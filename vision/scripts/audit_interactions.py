"""Snapshot visible course messages, separating humans from agent coordination.

Reads only the explicitly selected session and its declared child sessions.
Encrypted bodies remain explicit gaps: no credential access or reconstruction.
Snapshots are exclusive; a small latest-audit pointer selects the report input.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

try:
    from vision.scripts.export_interactions import scrub
except ModuleNotFoundError:
    from export_interactions import scrub

COORDINATION = {'spawn_agent','send_message','followup_task','interrupt_agent'}
EXCLUDED = ('<environment_context>','<external_codex_apps_open_page>','# AGENTS.md instructions')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_events(path):
    data=path.read_bytes(); rows=[]; errors=[]
    for number,line in enumerate(data.decode('utf-8-sig').splitlines(),1):
        try: rows.append((number,json.loads(line)))
        except json.JSONDecodeError: errors.append(number)
    return rows,{'file':path.name,'sha256':digest(data),'bytes':len(data),'parse_error_lines':errors}


def message_text(content):
    text='\n'.join(p.get('text','') for p in content if p.get('type') in ('input_text','output_text'))
    return text,any(p.get('type')=='encrypted_content' for p in content)


def classify(thread,role):
    if thread=='/root':
        return ('student_main','student','main_agent') if role=='user' else ('student_main','main_agent','student')
    return ('agent_collaboration','main_agent',thread) if role=='user' else ('agent_collaboration',thread,'main_agent')


def collect(session_file):
    queue=[(session_file,'/root')];visited=set();messages=[];sources=[];calls={};spawns=[];receipts=[]
    while queue:
        path,thread=queue.pop(0)
        if path in visited:continue
        visited.add(path);events,source=read_events(path);source['thread']=thread;sources.append(source)
        model='unknown';source['models']=[]
        for line,item in events:
            payload=item.get('payload',{});kind=item.get('type');typ=payload.get('type');stamp=item.get('timestamp')
            if kind=='turn_context':
                model=payload.get('model',model)
                if model not in source['models']:source['models'].append(model)
            if kind=='event_msg' and typ=='sub_agent_activity':
                identifier=payload.get('agent_thread_id','')
                if re.fullmatch(r'[0-9a-f-]{36}',identifier):
                    queue.extend((p,payload.get('agent_path',identifier)) for p in path.parent.glob('*'+identifier+'.jsonl'))
            base={'timestamp':stamp,'thread':thread,'source_file':path.name,'source_line':line}
            def add(text,category,sender,recipient,record_kind,**extra):
                text,redactions=scrub(text)
                messages.append(dict(base,category=category,sender=sender,recipient=recipient,kind=record_kind,
                                     model='not_applicable_human' if sender=='student' else model,
                                     text=text,redactions=redactions,**extra))
            if kind=='response_item' and typ=='function_call':
                name=payload.get('name','').split('.')[-1]
                if name not in COORDINATION|{'request_user_input','request_user_input_async'}:continue
                try:args=json.loads(payload.get('arguments','{}'))
                except (ValueError,TypeError):continue
                calls[payload.get('call_id')]=(name,thread,args)
                if name.startswith('request_user_input'):
                    add(json.dumps(args,ensure_ascii=False,indent=2),'student_main','main_agent','student','structured_question',call_id=payload.get('call_id'))
                else:
                    target=args.get('target',args.get('task_name','unknown'))
                    body=args.get('message','');encrypted=isinstance(body,str) and body.startswith('gAAAAA')
                    metadata={k:v for k,v in args.items() if k!='message'}
                    if name=='spawn_agent':spawns.append(dict(base,**metadata))
                    add('[原文缺口：会话持久化日志仅提供加密正文，未读取密钥或猜测还原。]' if encrypted else body,
                        'agent_collaboration',thread,target,'coordination_'+name,call_id=payload.get('call_id'),
                        metadata=metadata,body_available=not encrypted)
                continue
            if kind=='response_item' and typ=='function_call_output' and payload.get('call_id') in calls:
                name,origin,args=calls[payload['call_id']]
                if name.startswith('request_user_input'):
                    value=payload.get('output','');value=value if isinstance(value,str) else json.dumps(value,ensure_ascii=False)
                    add(value,'student_main','student','main_agent','structured_answer',call_id=payload['call_id'])
                continue
            if kind=='response_item' and typ=='agent_message':
                text,encrypted=message_text(payload.get('content',[]))
                sender=re.search(r'^Sender: (.+)$',text,re.M);recipient=payload.get('recipient',thread)
                body=text.split('Payload:\n',1)[-1] if 'Payload:\n' in text else text
                if encrypted:
                    receipts.append(dict(base,sender=sender.group(1) if sender else 'unknown',recipient=recipient,body_available=False))
                elif body.strip():
                    add(body,'agent_collaboration',sender.group(1) if sender else 'unknown',recipient,'delivered_agent_message',body_available=True)
                continue
            role=None;phase=None;text=''
            if kind=='event_msg' and typ in ('user_message','agent_message'):
                role='user' if typ=='user_message' else 'assistant';phase=payload.get('phase');text=payload.get('message','')
            elif kind=='response_item' and typ=='message':
                role=payload.get('role');phase=payload.get('channel',payload.get('phase'))
                text,encrypted=message_text(payload.get('content',[]))
            if role not in ('user','assistant') or role=='assistant' and phase not in (None,'commentary','final','final_answer'):continue
            if not isinstance(text,str) or not text.strip() or text.startswith(EXCLUDED):continue
            category,sender,recipient=classify(thread,role)
            add(text,category,sender,recipient,'visible_message',phase=phase,body_available=True)
    thread_models={s['thread']:s['models'][-1] if s['models'] else 'unknown' for s in sources}
    for row in messages:
        if row['sender'] not in ('student','main_agent'):
            row['model']=thread_models.get(row['sender'],row['model'])
        if row['recipient']=='/root':row['recipient']='main_agent'
    delivery_mirrors=set()
    for row in messages:
        if row['kind']!='delivered_agent_message':continue
        matching=[other for other in messages if other['kind']=='visible_message' and
                  (other['sender'],other['recipient'],other['text'])==(row['sender'],row['recipient'],row['text'])]
        if matching:
            # A delivery event is a mirror of an existing agent response, not a
            # new author turn. Keep its source as provenance on the response.
            matching[0].setdefault('mirror_sources',[]).append({'file':row['source_file'],'line':row['source_line']})
            delivery_mirrors.add((row['source_file'],row['source_line']))
    messages=[r for r in messages if (r['source_file'],r['source_line']) not in delivery_mirrors]
    # Remove event/response mirrors only when text, origin and time coincide;
    # preserve genuinely repeated prompts in later turns.
    result=[];recent={}
    for row in sorted(messages,key=lambda r:(r.get('timestamp') or '',r['source_file'],r['source_line'])):
        key=(row['sender'],row['recipient'],row['text'])
        stamp=datetime.fromisoformat(row['timestamp'].replace('Z','+00:00')).timestamp()
        previous=recent.get(key)
        if previous and abs(stamp-previous[0])<2:
            previous[1].setdefault('mirror_sources',[]).append({'file':row['source_file'],'line':row['source_line']});continue
        row['id']=digest((row['source_file']+str(row['source_line'])+row['text']).encode())
        result.append(row);recent[key]=(stamp,row)
    return result,sources,spawns,receipts


def snapshot(session_file,output_prefix):
    output_prefix=Path(output_prefix);transcript=output_prefix.with_suffix('.jsonl');audit_path=output_prefix.with_suffix('.audit.json')
    if transcript.exists() or audit_path.exists():raise FileExistsError('Choose a new snapshot prefix')
    rows,sources,spawns,receipts=collect(Path(session_file))
    output_prefix.parent.mkdir(parents=True,exist_ok=True)
    with transcript.open('x',encoding='utf-8') as stream:
        for row in rows:stream.write(json.dumps(row,ensure_ascii=False)+'\n')
    main=[r for r in rows if r['category']=='student_main'];agents=[r for r in rows if r['category']=='agent_collaboration']
    gaps=[{'record_id':r['id'],'timestamp':r['timestamp'],'sender':r['sender'],'recipient':r['recipient'],'kind':r['kind']} for r in agents if r.get('body_available') is False]
    questions=[r for r in main if r['kind']=='structured_question'];answers=[r for r in main if r['kind']=='structured_answer']
    models={source['thread']:source['models'] for source in sources}
    audit={'schema_version':2,'created_utc':datetime.now(timezone.utc).isoformat(),'transcript_path':str(transcript),
           'transcript_sha256':digest(transcript.read_bytes()),'coverage':'explicit main session and declared children; visible text only; snapshot cut-off',
           'sources':sources,'counts':{'student_main_records':len(main),'student_free_text_prompts':sum(r['sender']=='student' and r['kind']=='visible_message' for r in main),
           'structured_question_batches':len(questions),'structured_answer_batches':len(answers),'main_agent_visible_replies':sum(r['sender']=='main_agent' and r['kind']=='visible_message' for r in main),
           'agent_coordination_records':len(agents),'unavailable_coordination_bodies':len(gaps),'encrypted_delivery_receipts':len(receipts)},
           'model_metadata_by_thread':models,'spawn_model_checks':spawns,'all_spawn_models_explicit_6_1_sol':bool(spawns) and all(x.get('model')=='gpt-6.1-sol' and x.get('fork_turns')=='none' for x in spawns),
           'record_gaps':gaps,'encrypted_receipts':receipts,'strict_full_history_complete':not gaps and not receipts and not any(s['parse_error_lines'] for s in sources),
           'student_and_agent_records_separated':True,'last_visible_message_utc':max((r['timestamp'] for r in rows),default=None),
           'limitations':['代理间加密正文未恢复；不把元数据或事后概述冒充原始提示词。','交互轮数按学生自由文本提示和结构化问答批次分别统计；子代理活动不计入学生轮数。','会话跨度不是学生劳动时长；下载、排队与并发任务不能从消息时间差精确拆分，未完整测量项记为未知。','模型名称来自会话元数据，学生提示的model字段不适用；子代理模型限制独立核验。']}
    audit_path.write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
    latest=output_prefix.parent/'interaction_audit_latest.json'
    latest.write_text(json.dumps({'audit_path':str(audit_path),'transcript_path':str(transcript)},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'audit_path':str(audit_path),'counts':audit['counts'],'strict_full_history_complete':audit['strict_full_history_complete'],'spawn_models_passed':audit['all_spawn_models_explicit_6_1_sol']},ensure_ascii=False))
    return audit


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session-file',type=Path,required=True);parser.add_argument('--output-prefix',type=Path,required=True)
    args=parser.parse_args();snapshot(args.session_file,args.output_prefix)
