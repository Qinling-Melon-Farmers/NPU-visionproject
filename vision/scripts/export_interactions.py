"""Export only visible messages from this project's local session logs.

Does not export system/developer messages, reasoning, credentials, or raw tool
payloads. The caller must pass the exact current session file, not a directory.
Existing transcript rows are retained; subsequent snapshots append new rows.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re


def scrub(text):
    rules = [
        (r'(?i)(https?://)[^\s/@:]+:[^\s/@]+@', r'\1[REDACTED]@'),
        (r'(?i)\b(Bearer\s+)[A-Za-z0-9._~-]{16,}', r'\1[REDACTED]'),
        (r'\b(?:sk-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b', '[REDACTED]'),
        (r'-----BEGIN [^-]*PRIVATE KEY-----[\s\S]*?-----END [^-]*PRIVATE KEY-----', '[REDACTED PRIVATE KEY]'),
    ]
    count=0
    for pattern,replacement in rules:
        text,n=re.subn(pattern,replacement,text)
        count+=n
    return text,count


def records(path):
    with path.open(encoding='utf-8') as stream:
        for line in stream:
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue  # An active session may have an unfinished final line.


def export(session_file, destination):
    queue=[session_file]; visited=set(); messages=[]
    while queue:
        path=queue.pop(0)
        if path in visited:
            continue
        visited.add(path)
        model='unknown'; model_calls={}
        for item in records(path):
            payload=item.get('payload',{})
            if item.get('type')=='turn_context':
                model=payload.get('model',model)
            if item.get('type')=='event_msg' and payload.get('type')=='sub_agent_activity':
                identifier=payload.get('agent_thread_id','')
                if re.fullmatch(r'[0-9a-f-]{36}',identifier):
                    queue.extend(path.parent.glob('*'+identifier+'.jsonl'))
            role=None; phase=None
            if item.get('type')=='event_msg' and payload.get('type') in ('user_message','agent_message'):
                role='user' if payload['type']=='user_message' else 'assistant'
                phase=payload.get('phase')
                if role=='assistant' and phase not in (None,'commentary','final','final_answer'):continue
                text=payload.get('message','')
            elif item.get('type')=='response_item' and payload.get('type')=='message':
                role=payload.get('role');phase=payload.get('channel',payload.get('phase'))
                if role not in ('user','assistant'):continue
                if role=='assistant' and phase not in (None,'commentary','final','final_answer'):continue
                text='\n'.join(part.get('text','') for part in payload.get('content',[]) if part.get('type') in ('input_text','output_text'))
                if text.startswith(('<environment_context>','<external_codex_apps_open_page>','# AGENTS.md instructions')):continue
            else:continue
            if not isinstance(text,str) or not text.strip():continue
            text,redactions=scrub(text)
            identifier=hashlib.sha256((path.name+str(item.get('timestamp'))+role+text).encode()).hexdigest()
            messages.append({'id':identifier,'timestamp':item.get('timestamp'),'role':role,'model':model,
                             'thread':'main' if path==session_file else path.stem[-36:],
                             'phase':phase,'text':text,'redactions':redactions,
                             'source':'local visible session event'})
    existing=set(); semantics=set()
    if destination.exists():
        for row in records(destination):
            existing.add(row.get('id'));semantics.add((row.get('thread'),row.get('role'),row.get('text')))
    destination.parent.mkdir(parents=True,exist_ok=True)
    added=0
    with destination.open('a',encoding='utf-8') as stream:
        for row in sorted(messages,key=lambda row:row.get('timestamp') or ''):
            semantic=(row['thread'],row['role'],row['text'])
            if row['id'] not in existing and semantic not in semantics:
                stream.write(json.dumps(row,ensure_ascii=False)+'\n');existing.add(row['id']);semantics.add(semantic);added+=1
    print(json.dumps({'threads':len(visited),'visible_messages_added':added,'total_records':len(existing),'path':str(destination)},ensure_ascii=True))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--session-file',type=Path,required=True)
    parser.add_argument('--output',type=Path,default=Path('vision/logs/interaction_transcript.jsonl'))
    args=parser.parse_args()
    export(args.session_file,args.output)
