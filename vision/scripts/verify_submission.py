"""Verify archive hashes and run imports from a fresh isolated extraction."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys
import zipfile


def verify(archive_path, destination):
    destination=Path(destination).resolve()
    if destination.exists():raise FileExistsError(destination)
    with zipfile.ZipFile(archive_path) as archive:
        manifest=json.loads(archive.read('submission_manifest.json'))
        entries={row['path']:row for row in manifest['files']}
        if len(entries)!=len(manifest['files']) or set(archive.namelist())!=set(entries)|{'submission_manifest.json'}:
            raise ValueError('Unexpected or duplicate archive entry')
        for name,row in entries.items():
            path=PurePosixPath(name)
            if path.is_absolute() or '..' in path.parts or '\\' in name or ':' in name:
                raise ValueError('Unsafe ZIP path')
            if path.suffix.lower() in {'.mp4','.pth','.pt','.h5','.npz','.pickle','.pkl'}:
                raise ValueError('Excluded large asset found')
            data=archive.read(name)
            if len(data)!=row['bytes'] or hashlib.sha256(data).hexdigest()!=row['sha256']:
                raise ValueError('Archive hash mismatch: '+name)
        destination.mkdir(parents=True)
        for name in archive.namelist():
            target=destination.joinpath(*PurePosixPath(name).parts)
            target.parent.mkdir(parents=True,exist_ok=True)
            with target.open('xb') as stream:stream.write(archive.read(name))
    programs={
        'image_author_import':"import sys;sys.path.insert(0,'vision/vendor/cirtorch');from cirtorch.layers.functional import gem,l2n;import torch;assert gem(torch.ones(1,3,4,4)).shape==(1,3,1,1);print('image import passed')",
        'video_author_import':"import sys;sys.path.insert(0,'vision/vendor/visil');from model.visil import ViSiL;print('video import passed')",
        'summary_author_import':"import sys;sys.path.insert(0,'vision/vendor/dsnet/src');from modules.model_zoo import get_model;print('summary import passed')",
    }
    checks=[]
    for name,program in programs.items():
        result=subprocess.run([sys.executable,'-s','-c',program],cwd=destination,text=True,capture_output=True,timeout=60)
        if result.returncode:raise RuntimeError(name+' failed: '+result.stderr)
        checks.append({'name':name,'status':'passed','stdout':result.stdout.strip()})
    result=subprocess.run([sys.executable,'-s','-m','vision','--help'],cwd=destination,text=True,capture_output=True,timeout=60)
    if result.returncode:raise RuntimeError('Extracted CLI failed: '+result.stderr)
    checks.append({'name':'extracted_cli','status':'passed'})
    return {'status':'passed','archive':str(Path(archive_path).resolve()),'sha256':hashlib.sha256(Path(archive_path).read_bytes()).hexdigest(),
            'files_verified':len(entries),'extracted_to':str(destination),'checks':checks,'report_scope':manifest['experiment_evidence']['report_record_scope']}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',type=Path,required=True);parser.add_argument('--extract-to',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():raise FileExistsError(args.output)
    result=verify(args.archive,args.extract_to)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))
