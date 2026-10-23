"""Run each visual experiment in its own isolated Python process."""
from __future__ import annotations

import argparse
import contextlib
import importlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone, timedelta

from vision.common.io import Tee, append_event, save_json, sha256

ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT.parent


def code_state():
    def git(*arguments):
        proc = subprocess.run(['git', *arguments], cwd=WORKSPACE, capture_output=True, text=True, encoding='utf-8', errors='replace')
        return proc.stdout.strip() if proc.returncode == 0 else None
    sources = {p.relative_to(WORKSPACE).as_posix(): sha256(p) for p in ROOT.rglob('*.py')
               if '.git' not in p.parts and '__pycache__' not in p.parts}
    return {'commit': git('rev-parse', 'HEAD'), 'working_tree': git('status', '--porcelain'), 'source_sha256': sources}


def main(argv=None):
    parser = argparse.ArgumentParser(description='Multimedia visual experiments; launch through the dedicated Conda environment.')
    parser.add_argument('command', choices=['prepare', 'image', 'video', 'summary', 'report', 'verify'])
    parser.add_argument('--config', type=Path, default=ROOT / 'configs/default.yaml')
    parser.add_argument('--run-id', default='visual-20261023')
    parser.add_argument('--target', choices=['all', 'image', 'video', 'summary'], default='all')
    parser.add_argument('--download', action='store_true', help='Fetch missing public resources when preparing')
    parser.add_argument('--video-stage', choices=['status','sources','clips'], default='status')
    args = parser.parse_args(argv)
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,79}', args.run_id):
        parser.error('run-id must be a simple ASCII directory name')
    import yaml
    cfg = yaml.safe_load(args.config.read_text(encoding='utf-8'))
    expected = Path(cfg['environment_prefix']).resolve()
    if Path(sys.prefix).resolve() != expected or not sys.flags.no_user_site:
        parser.error('Use conda run -p <configured environment_prefix> python -s -m vision ...')
    os.environ['TORCH_HOME'] = str(Path(cfg['asset_root']) / 'cache/torch')
    os.environ['MPLCONFIGDIR'] = str(Path(cfg['asset_root']) / 'cache/matplotlib')
    os.environ['PYTHONNOUSERSITE'] = '1'
    experiment_root = ROOT / 'outputs' / args.run_id
    experiment_root.mkdir(parents=True, exist_ok=True)
    if args.command in ('image', 'video', 'summary'):
        destination = experiment_root / args.command
        if destination.exists() and any(destination.iterdir()):
            parser.error(f'{destination} already contains evidence; use a new run-id')
    stamp = datetime.now(timezone(timedelta(hours=8))).strftime('%Y%m%dT%H%M%S%f')
    logfile = ROOT / 'logs' / f'{args.run_id}_{args.command}_{stamp}.log'
    metadata = {'run_id': args.run_id, 'command': sys.argv, 'started_at': stamp, 'config': cfg,
                'interpreter': sys.executable, 'python': sys.version, 'code': code_state(),
                'status': 'running', 'log': str(logfile.relative_to(WORKSPACE))}
    started = time.monotonic()
    with logfile.open('w', encoding='utf-8') as stream, contextlib.redirect_stdout(Tee(sys.stdout, stream)), contextlib.redirect_stderr(Tee(sys.stderr, stream)):
        try:
            if args.command == 'prepare':
                if args.download:
                    from vision.common.resources import ensure_resources
                    ensure_resources(cfg)
                targets = ['image', 'video', 'summary'] if args.target == 'all' else [args.target]
                result = {}
                for target in targets:
                    module = importlib.import_module(f'vision.experiments.{target}')
                    if target == 'video' and args.video_stage != 'status':
                        result[target] = getattr(module, 'prepare_' + args.video_stage)(cfg)
                    else:
                        result[target] = module.prepare(cfg)
                save_json(experiment_root / f'preparation_{stamp}.json', result)
            elif args.command == 'report':
                from vision.reports.build_report import build
                report_path = ROOT / 'reports' / f'视觉实验报告_{args.run_id}_{stamp}.docx'
                result = build(cfg, experiment_root, report_path)
                save_json(experiment_root / f'report_{stamp}.json', result)
            elif args.command == 'verify':
                from vision.common.verify import verify
                result = verify(cfg, experiment_root)
                save_json(experiment_root / f'verification_{stamp}.json', result)
            else:
                module = importlib.import_module(f'vision.experiments.{args.command}')
                result = module.run(cfg, experiment_root / args.command)
            metadata['status'] = 'completed'
            print(json.dumps({'command': args.command, 'status': 'completed', 'run_id': args.run_id}, ensure_ascii=False))
        except Exception as error:
            metadata.update(status='failed', error=f'{type(error).__name__}: {error}')
            traceback.print_exc()
        finally:
            metadata['elapsed_seconds'] = time.monotonic() - started
            save_json(experiment_root / f'{args.command}_run_{stamp}.json', metadata)
            append_event(ROOT / 'logs/run_events.jsonl', {k: v for k, v in metadata.items() if k != 'code'})
    return 0 if metadata['status'] == 'completed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
