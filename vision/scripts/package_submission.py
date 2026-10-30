"""Select source files and one final report into a reproducible submission ZIP.

Usage: python -s vision/scripts/package_submission.py --run-root RUN_DIR
 --report FINAL.docx --output submission.zip [--dry-run]
No datasets, weights, features, videos, Git metadata or logs are selected.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import zipfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRS = ('common','experiments','configs','tests','scripts','vendor','manifests','reports')
SOURCE_SUFFIXES = {'.py','.md','.txt','.yml','.yaml','.toml','.cfg','.ini','.json','.sh','.bat','.ps1','.rst','.in'}
BLOCKED_PARTS = {'.git','.hg','.svn','__pycache__','.pytest_cache','data','datasets','weights','models','features','cache','downloads','outputs','logs','custom_data','custom_dataset'}
SECRET_NAME = re.compile(r'(^\.env($|\.)|credentials|secrets?|token|id_rsa|id_ed25519|\.pem$|\.key$)',re.I)
SECRET_CONTENT = re.compile(rb'-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----|(?:AKIA|ASIA)[A-Z0-9]{16}|gh[pousr]_[A-Za-z0-9]{30,}|sk-[A-Za-z0-9_-]{32,}')

def digest(path):
    result=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(8*1024*1024),b''):
            result.update(block)
    return result.hexdigest()

def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

def check_results(run_root):
    status={}
    for name in ('image','video','summary'):
        path=run_root/name/'results.json'
        if not path.is_file():
            raise ValueError(f'Missing experiment result: {path}')
        result=read_json(path)
        if result.get('status')!='completed':
            raise ValueError(f'Experiment incomplete: {name}')
        if name=='image' and not result.get('methods'):
            raise ValueError('Image result has no evaluated methods')
        if name=='video' and not result.get('queries'):
            raise ValueError('Video result has no evaluated queries')
        status[name]={'sha256':digest(path),'status':result['status']}
    summary=read_json(run_root/'summary/results.json')
    rows=summary.get('results',[])
    if not rows or not any(abs(float(r['budget'])-.15)<1e-8 for r in rows):
        raise ValueError('Missing nonempty 15% summary results')
    for row in rows:
        selected,total=int(row['selected_frames']),int(row['total_frames'])
        if total<=0 or selected<=0 or selected>int(total*min(.15,float(row['budget']))):
            raise ValueError('Summary frame budget invalid')
        if selected!=int(row['export']['export_decoded_frames']):
            raise ValueError('Summary export count mismatch')
        if abs(float(row['ratio'])-selected/total)>1e-10:
            raise ValueError('Summary ratio inconsistent')
    review_path=run_root/'summary/playback_review.json'
    if not review_path.is_file() or read_json(review_path).get('status')!='passed':
        raise ValueError('Actual playback review is missing or not passed')
    status['playback_review']={'sha256':digest(review_path),'status':'passed'}
    for name in ('image','video','summary'):
        path=run_root/f'replay_{name}.json'
        if not path.is_file() or read_json(path).get('status')!='passed':
            raise ValueError(f'Independent model replay missing or failed: {name}')
        status[f'replay_{name}']={'sha256':digest(path),'status':'passed'}
    return status

def select_sources():
    selected=[]
    for directory in SOURCE_DIRS:
        base=ROOT/directory
        if not base.exists():
            continue
        for path in sorted(base.rglob('*')):
            relative=path.relative_to(ROOT)
            blocked=any(p.lower() in BLOCKED_PARTS for p in relative.parts)
            # Some author Python packages are named datasets/models; they are
            # import dependencies, not downloaded dataset/weight assets.
            vendor_module=directory=='vendor' and path.suffix.lower()=='.py' and not any(p.lower() in {'.git','__pycache__','custom_data','custom_dataset'} for p in relative.parts)
            if not path.is_file() or path.is_symlink() or blocked and not vendor_module:
                continue
            if directory=='reports' and path.suffix!='.py' and path.name!='INTERACTION_AUDIT.md':
                continue
            if path.suffix.lower() not in SOURCE_SUFFIXES and path.name.upper() not in {'LICENSE','COPYING','NOTICE','AUTHORS','MAKEFILE'}:
                continue
            if SECRET_NAME.search(path.name):
                raise ValueError(f'Credential-like filename in selected source: {relative}')
            if SECRET_CONTENT.search(path.read_bytes()):
                raise ValueError(f'Credential-like content in selected source: {relative}')
            selected.append(path)
    for path in sorted(ROOT.iterdir()):
        if path.is_file() and (path.name in {'__init__.py','__main__.py','README.md','environment.yml','environment.yaml'} or
           ('lock' in path.name.lower() or 'explicit' in path.name.lower()) and path.suffix.lower() in {'.txt','.yml','.yaml','.json'}):
            if SECRET_CONTENT.search(path.read_bytes()):
                raise ValueError(f'Credential-like content: {path.name}')
            selected.append(path)
    if not any(p.name.lower()=='readme.md' and p.parent==ROOT for p in selected):
        raise ValueError('Required vision/README.md missing')
    return sorted(set(selected))

def package(run_root,report,output,dry_run=False):
    run_root,report,output=map(lambda p:Path(p).resolve(),(run_root,report,output))
    if output.exists():
        raise FileExistsError(output)
    if output.suffix.lower()!='.zip' or report.suffix.lower()!='.docx' or not report.is_file():
        raise ValueError('Require an existing DOCX report and new ZIP output')
    status=check_results(run_root)
    with zipfile.ZipFile(report) as archive:
        if 'word/document.xml' not in archive.namelist():
            raise ValueError('Report is not a valid Word document')
        document=ET.fromstring(archive.read('word/document.xml'))
        ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        paragraphs=[''.join(t.text or '' for t in p.findall('.//w:t',ns)) for p in document.findall('.//w:p',ns)]
        cover_status=next((p for p in paragraphs if p.startswith('报告状态：')),None)
        if cover_status is None:
            # The 2026-10-28 report uses a school-style cover without a
            # status line. Accept it only when the title and appendices are
            # present; the strict-history flag stays false because the
            # encrypted agent records remain a known gap.
            required=('多媒体技术','实验报告','附录 C','附录 D')
            if not all(any(token in p for p in paragraphs) for token in required):
                raise ValueError('Report is not the final multimedia report')
            status['report_record_scope']={'cover_status':'无独立报告状态行；按标题和附录 C/D 判断','strict_history_complete':False}
        else:
            if '待完成草稿' in cover_status:
                raise ValueError('Report is marked as an incomplete draft')
            status['report_record_scope']={'cover_status':cover_status,'strict_history_complete':'历史原文缺口' not in cover_status}
    sources=select_sources()
    entries=[(p,'vision/'+p.relative_to(ROOT).as_posix()) for p in sources]+[(report,'report/'+report.name)]
    manifest={'created_utc':datetime.now(timezone.utc).isoformat(),'selection':'source allowlist plus explicitly selected final DOCX; excludes datasets, weights, features, videos, logs, Git and credentials','experiment_evidence':status,'files':[{'path':name,'bytes':path.stat().st_size,'sha256':digest(path)} for path,name in entries]}
    if not dry_run:
        output.parent.mkdir(parents=True,exist_ok=True)
        # Exclusive creation protects all existing archives.
        with zipfile.ZipFile(output,'x',compression=zipfile.ZIP_DEFLATED) as archive:
            for path,name in entries:
                archive.write(path,name)
            archive.writestr('submission_manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2))
    return {'dry_run':dry_run,'output':str(output),'file_count':len(entries),'source_bytes':sum(x['bytes'] for x in manifest['files']),'manifest':manifest}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for argument in ('run-root','report','output'):
        parser.add_argument('--'+argument,required=True)
    parser.add_argument('--dry-run',action='store_true')
    args=parser.parse_args()
    print(json.dumps(package(args.run_root,args.report,args.output,args.dry_run),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
