"""Anonymous, non-destructive public-resource reconstruction (standard library)."""
from pathlib import Path, PurePosixPath
import hashlib
import http.client
import json
import re
import shutil
import tarfile
import time
import urllib.request
import urllib.parse
import uuid
import zipfile

ROOT = Path(__file__).resolve().parents[1]

def sha256(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''): digest.update(chunk)
    return digest.hexdigest()

def _url(url):
    parsed=urllib.parse.urlsplit(url)
    if parsed.scheme not in ('https','http') or parsed.username or parsed.password:
        raise ValueError('Only public HTTP(S) URLs without credentials are allowed')
    return url

class PublicRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _url(newurl)
        return super().redirect_request(req,fp,code,msg,headers,newurl)

def download(url, destination, expected_sha256=None, retries=5, opener=None):
    """Reuse verified finals; resume only with matching URL/validator metadata.

    Servers ignoring Range start a distinct temporary file. Existing final files
    are never overwritten or deleted, including when their hash is wrong.
    """
    _url(url); destination=Path(destination); destination.parent.mkdir(parents=True,exist_ok=True)
    if destination.exists():
        actual=sha256(destination)
        if expected_sha256 and actual != expected_sha256.lower():
            raise ValueError(f'Existing resource SHA256 mismatch; retained unchanged: {destination}')
        if not expected_sha256:
            raise ValueError(f'Existing resource has no trusted expected hash; inspect and record it first: {destination}')
        return {'path':str(destination),'sha256':actual,'reused':True,'url':url}
    # Explicitly omit proxy, Cookie and authentication handlers; never read netrc/browser state.
    opener=opener or urllib.request.build_opener(urllib.request.ProxyHandler({}),PublicRedirect())
    part=destination.with_name(destination.name+'.part')
    metadata=part.with_name(part.name+'.json')
    state={}
    if part.exists() and metadata.exists():
        state=json.loads(metadata.read_text(encoding='utf-8'))
    if part.exists() and (state.get('url') != url or not state.get('validator')):
        part=destination.with_name(destination.name+'.'+uuid.uuid4().hex+'.part')
        metadata=part.with_name(part.name+'.json');state={}
    last=None
    for attempt in range(retries):
        offset=part.stat().st_size if part.exists() else 0
        headers={'User-Agent':'MultimediaCourseResourcePreparation/1.0','Accept-Encoding':'identity'}
        if offset and state.get('validator'):
            headers.update({'Range':f'bytes={offset}-','If-Range':state['validator']})
        try:
            with opener.open(urllib.request.Request(url,headers=headers),timeout=90) as response:
                status=response.status
                if status not in (200,206):raise ValueError(f'Unexpected HTTP status {status}')
                validator=response.headers.get('ETag') or response.headers.get('Last-Modified')
                if offset:
                    content_range=response.headers.get('Content-Range','')
                    match=re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)',content_range)
                    if status != 206 or not match or int(match[1]) != offset or validator != state.get('validator'):
                        # Preserve the interrupted file. A full 200 response is usable in a new file.
                        part=destination.with_name(destination.name+'.'+uuid.uuid4().hex+'.part')
                        metadata=part.with_name(part.name+'.json');offset=0
                        if status != 200: raise ValueError('Server returned an invalid partial response')
                state={'url':url,'validator':validator}
                metadata.write_text(json.dumps(state),encoding='utf-8')
                length=response.headers.get('Content-Length')
                received=0
                with part.open('ab' if offset else 'xb') as target:
                    while True:
                        chunk=response.read(1024*1024)
                        if not chunk: break
                        target.write(chunk);received+=len(chunk)
                if length is not None and received != int(length): raise IOError('Incomplete HTTP body')
            actual=sha256(part)
            if expected_sha256 and actual != expected_sha256.lower():
                raise ValueError(f'Download SHA256 mismatch; temporary retained: {part}')
            # Windows rename refuses an existing destination and avoids duplicating large temporary files.
            if destination.exists():raise FileExistsError(destination)
            part.rename(destination)
            return {'path':str(destination),'sha256':actual,'reused':False,'url':url,
                    'expected_sha256_known':bool(expected_sha256)}
        except (OSError,ValueError,http.client.HTTPException) as error:
            last=error
            if destination.exists(): raise
            if isinstance(error,ValueError) and 'SHA256 mismatch' in str(error): raise
            if attempt+1<retries: time.sleep(min(2**attempt,8))
    raise RuntimeError(f'Public resource download failed after {retries} attempts: {url}; {last}') from last

def safe_member_path(root,name):
    """Reject traversal, Windows drives/ADS, symlinks and case-insensitive escapes."""
    name=name.replace('\\','/')
    relative=PurePosixPath(name)
    if relative.is_absolute() or '..' in relative.parts or any(':' in p for p in relative.parts):
        raise ValueError(f'Unsafe archive member: {name}')
    root=Path(root).resolve();target=root.joinpath(*relative.parts).resolve()
    if target != root and root not in target.parents: raise ValueError(f'Archive path escapes root: {name}')
    return target

def _copy_member(source,target):
    """Skip identical extracted files and reject changes without overwriting."""
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists():
        digest=hashlib.sha256()
        for chunk in iter(lambda:source.read(1024*1024),b''):digest.update(chunk)
        if digest.hexdigest()!=sha256(target): raise ValueError(f'Existing extracted member differs; retained: {target}')
        return
    temporary=target.with_name(target.name+'.extract-'+uuid.uuid4().hex+'.part')
    with temporary.open('xb') as output: shutil.copyfileobj(source,output)
    if target.exists():raise FileExistsError(target)
    temporary.rename(target)

def extract_archive(archive,root,select=None):
    """select(name) returns destination relative path or None to omit a member."""
    archive=Path(archive);root=Path(root);written=[]
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as container:
            for member in container.infolist():
                safe_member_path(root,member.filename)
                if (member.external_attr>>16)&0o170000 == 0o120000: raise ValueError('Archive symlink forbidden')
                name=select(member.filename) if select else member.filename
                if name is None or member.is_dir():continue
                target=safe_member_path(root,name)
                with container.open(member) as source:_copy_member(source,target)
                written.append(str(target))
    else:
        with tarfile.open(archive,'r:*') as container:
            for member in container:
                safe_member_path(root,member.name)
                if member.issym() or member.islnk() or member.isdev():raise ValueError('Archive links/devices forbidden')
                name=select(member.name) if select else member.name
                if name is None or not member.isfile():continue
                target=safe_member_path(root,name)
                with container.extractfile(member) as source:_copy_member(source,target)
                written.append(str(target))
    return written

def _load(name):
    path=ROOT/'manifests'/name
    if not path.exists():raise FileNotFoundError(f'Resource source manifest missing: {path}')
    return json.loads(path.read_text(encoding='utf-8-sig'))

def ensure_resources(cfg):
    """Sequentially reconstruct resources; never install environments or run models."""
    root=Path(cfg['asset_root']); root.mkdir(parents=True,exist_ok=True)
    image=_load('image_sources.json');summary=_load('summary_sources.json');video=_load('video_resources.json')
    if not (ROOT/'vendor'/'cirtorch'/'cirtorch'/'layers'/'functional.py').is_file():
        raise FileNotFoundError('Missing bundled cirtorch author source')
    for item in ['dsnet/src/anchor_free/dsnet_af.py','dsnet/splits/tvsum.yml',*video.get('required_vendor_files',[])]:
        source=ROOT/item if item.startswith('vendor/') else ROOT/'vendor'/item
        if not source.is_file():raise FileNotFoundError(f'Missing bundled author source: {item}')
    records=[]
    def obtain(url,relative,digest=None):
        item=download(url,root/relative,digest);records.append(item);return Path(item['path'])
    coil=obtain(image['dataset']['download_url'],'downloads/coil-100.zip',image['dataset']['archive_sha256'])
    extract_archive(coil,root/'data'/'coil-100')
    obtain(image['weight']['download_url'],image['weight']['local_path_relative_to_asset_root'],image['weight']['sha256'])
    for item in video['resources']:
        path=obtain(item['url'],item['path'],item.get('sha256'))
        if item.get('extract_to'):
            extracted=extract_archive(path,root/item['extract_to'])
            for nested in extracted:
                if Path(nested).suffix.lower()=='.zip':
                    extract_archive(nested,root/item.get('nested_extract_to',item['extract_to']))
    archives={Path(item['path']).name:item for item in summary['files']}
    datasets=obtain(summary['datasets_url'],'downloads/dsnet_datasets.zip',archives['dsnet_datasets.zip']['sha256'])
    extract_archive(datasets,root/'data'/'dsnet',lambda n:Path(n).name if Path(n).name in
        ('eccv16_dataset_tvsum_google_pool5.h5','tvsum_splits.json') else None)
    weights=obtain(summary['weights_url'],'downloads/dsnet_pretrain_af_basic.zip',archives['dsnet_pretrain_af_basic.zip']['sha256'])
    split_index=int(cfg.get('summary',{}).get('split_index',0))
    if split_index not in range(5):raise ValueError('DSNet official TVSum split_index must be 0..4')
    extract_archive(weights,root/'weights'/'dsnet',lambda n:n if n.endswith(f'/checkpoint/tvsum.yml.{split_index}.pt') else None)
    evidence=root/'resource_verification'
    evidence.mkdir(exist_ok=True)
    output=evidence/(time.strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:8]+'.json')
    output.write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
    return {'status':'resources_verified','resources':records,'verification_manifest':str(output)}

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description='匿名下载并核验课程公开资源（不安装环境）')
    parser.add_argument('--asset-root',required=True)
    args=parser.parse_args()
    print(json.dumps(ensure_resources({'asset_root':args.asset_root}),ensure_ascii=False,indent=2))
