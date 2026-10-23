"""Resume and verify approved official Conda downloads; never install packages."""
import concurrent.futures
import hashlib
import json
from pathlib import Path
import subprocess
import threading
import time
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
CACHE = Path(r'E:\MultimediaCourseAssets\conda-pkgs')
LOG = ROOT/'logs/conda-prefetch.log'
LOCK = threading.Lock()

def log(message):
    with LOCK:
        line = f'{time.strftime("%Y-%m-%dT%H:%M:%S")} {message}'
        print(line, flush=True)
        with LOG.open('a', encoding='utf-8') as stream:
            stream.write(line+'\n')

def valid(path, record):
    if not path.is_file() or path.stat().st_size != int(record['size']):
        return False
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(8*1024*1024), b''):
            digest.update(block)
    return digest.hexdigest() == record['sha256']

def fetch(record):
    filename = record['fn']
    if Path(filename).name != filename:
        raise ValueError('Unsafe archive name')
    parsed = urlsplit(record['url'])
    allowed = (parsed.hostname == 'repo.anaconda.com' or
               (parsed.hostname == 'conda.anaconda.org' and parsed.path.split('/')[1] in ['pytorch','nvidia']))
    if parsed.scheme != 'https' or parsed.username or parsed.password or parsed.query or not allowed:
        raise ValueError(f'Unapproved source: {filename}')
    destination = CACHE/filename
    if valid(destination, record):
        log(f'VERIFIED_EXISTING {filename}')
        return True
    if destination.exists():
        log(f'CONFLICT preserving invalid existing archive {filename}')
        return False
    partial = CACHE/(filename+'.partial')
    for attempt in range(1,11):
        if valid(partial,record):
            # rename cannot replace an existing archive on Windows.
            partial.rename(destination)
            log(f'VERIFIED_COMPLETE {filename} bytes={record["size"]}')
            return True
        if partial.exists() and partial.stat().st_size >= int(record['size']):
            log(f'PRESERVE_INVALID_PARTIAL {partial.name}')
            partial = CACHE/(filename+f'.prefetch-{time.time_ns()}.partial')
        start = partial.stat().st_size if partial.exists() else 0
        log(f'DOWNLOAD {filename} attempt={attempt} offset={start}')
        result = subprocess.run(['curl.exe','-q','--fail','-L','-C','-',
            '--connect-timeout','30','--max-time','180','--silent','--show-error',
            record['url'],'-o',str(partial)],capture_output=True,text=True)
        log(f'CURL {filename} exit={result.returncode} bytes={partial.stat().st_size if partial.exists() else 0} detail={result.stderr.strip()[:500]}')
        if result.returncode == 33:
            # Keep the old partial intact if the server does not honor Range.
            partial = CACHE/(filename+f'.prefetch-{time.time_ns()}.partial')
    if valid(partial,record):
        partial.rename(destination)
        log(f'VERIFIED_COMPLETE {filename} bytes={record["size"]}')
        return True
    log(f'FAILED_RETRY_LIMIT {filename}')
    return False

def main():
    payload=(ROOT/'logs/conda-solve.json').read_bytes()
    records=json.loads(payload.decode('utf-16' if payload[:2] in [b'\xff\xfe',b'\xfe\xff'] else 'utf-8-sig'))['actions']['FETCH']
    CACHE.mkdir(parents=True,exist_ok=True)
    log(f'START packages={len(records)} workers=4 download_only=true')
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(fetch,records))
    log(f'FINISH verified={sum(results)} total={len(results)}')
    return 0 if all(results) else 1

if __name__=='__main__':
    raise SystemExit(main())
