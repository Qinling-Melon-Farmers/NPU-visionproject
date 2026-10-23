"""Check a generated DOCX against the exact classified interaction snapshot."""
import argparse
import hashlib
import json
from pathlib import Path

from docx import Document


def verify_report(report, audit_path):
    audit=json.loads(Path(audit_path).read_text(encoding='utf-8-sig'))
    snapshot=Path(audit['transcript_path']);raw=snapshot.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=audit['transcript_sha256']:
        raise ValueError('Interaction snapshot hash changed')
    rows=[json.loads(line) for line in raw.decode('utf-8-sig').splitlines() if line.strip()]
    doc=Document(report);paragraphs=doc.paragraphs
    starts={p.text:i for i,p in enumerate(paragraphs) if p.style.name=='Heading 1'}
    c=starts['附录 C 学生与主代理的可见交互原文'];d=starts['附录 D 代理协作记录及不可恢复原文清单']
    student_text='\n'.join(p.text for p in paragraphs[c:d]);agent_text='\n'.join(p.text for p in paragraphs[d:])
    for row in rows:
        correct=student_text if row['category']=='student_main' else agent_text
        wrong=agent_text if row['category']=='student_main' else student_text
        if row['id'] not in correct or row['text'].replace('\r\n','\n') not in correct:
            raise ValueError('Missing complete visible text or record ID: '+row['id'])
        if row['id'] in wrong:raise ValueError('Record appears in wrong appendix: '+row['id'])
    cover=next(p.text for p in paragraphs if p.text.startswith('报告状态：'))
    if not audit['strict_full_history_complete'] and '历史原文缺口' not in cover:
        raise ValueError('Cover hides interaction-history limitation')
    if len(doc.inline_shapes)!=32:raise ValueError('Unexpected embedded figure count')
    if 'gAAAAA' in student_text+agent_text:raise ValueError('Encrypted body should not be exported')
    return {'status':'passed','report':str(Path(report).resolve()),'report_sha256':hashlib.sha256(Path(report).read_bytes()).hexdigest(),
            'snapshot_sha256':audit['transcript_sha256'],'verified_records':len(rows),'embedded_figures':len(doc.inline_shapes),
            'student_agent_appendices_separate':True,'full_visible_text_verified':True,
            'strict_history_complete':audit['strict_full_history_complete'],'cover_status':cover,
            'scope':'Document-to-snapshot fidelity, not recovery of encrypted historical text'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path,required=True);parser.add_argument('--audit',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():raise FileExistsError(args.output)
    result=verify_report(args.report,args.audit)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))
