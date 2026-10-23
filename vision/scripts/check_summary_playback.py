"""Audit export order and play all summaries through FFplay's offscreen renderer.

This is an agent/tool review, not a claim that a human watched the videos.
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
import numpy as np
import cv2
from vision.common.media import iter_frames, probe_video
from vision.common.io import sha256, save_json

parser=argparse.ArgumentParser()
parser.add_argument('--run-root',type=Path,required=True)
args=parser.parse_args()
directory=args.run_root/'summary'
destination=directory/'playback_review.json'
if destination.exists():raise FileExistsError(destination)
result=json.loads((directory/'results.json').read_text(encoding='utf-8'))
audits=[]
for row in result['results']:
    budget=round(row['budget']*100)
    mask=np.load(directory/f'summary_{budget:02d}.npz')['mask']
    decoded=iter_frames(row['export']['path'])
    count=0;errors=[]
    try:
        for frame_index,frame in enumerate(iter_frames(result['video_path'])):
            if mask[frame_index]:
                exported=next(decoded)
                original_small=cv2.resize(frame,(64,48),interpolation=cv2.INTER_AREA).astype(float)
                exported_small=cv2.resize(exported,(64,48),interpolation=cv2.INTER_AREA).astype(float)
                errors.append(float(np.mean(abs(original_small-exported_small))))
                count+=1
        try:next(decoded);raise RuntimeError('Unexpected extra exported frame')
        except StopIteration:pass
    finally:decoded.close()
    assert count==row['selected_frames']
    assert max(errors)<8, f'Potential wrong frame order: MAE={max(errors)}'
    path=Path(row['export']['path'])
    log=directory/f'ffplay_{budget:02d}.log'
    if log.exists():raise FileExistsError(log)
    env=os.environ.copy();env['SDL_VIDEODRIVER']='dummy';env['SDL_RENDER_DRIVER']='software'
    command=[str(Path(sys.prefix)/'Library/bin/ffplay.exe'),'-hide_banner','-loglevel','info','-autoexit','-an','-vf','showinfo',str(path)]
    started=time.monotonic()
    with log.open('wb') as stream:
        process=subprocess.run(command,stdout=subprocess.DEVNULL,stderr=stream,env=env,timeout=probe_video(path)['duration']+30,creationflags=subprocess.CREATE_NO_WINDOW)
    elapsed=time.monotonic()-started
    text=log.read_text(encoding='utf-8',errors='replace')
    frame_ids=[int(i) for i in re.findall(r'\bn:\s*(\d+)\s+pts:',text)]
    assert process.returncode==0 and frame_ids==list(range(count))
    assert elapsed>=.9*count/row['export']['fps']
    audits.append({'path':str(path.resolve()),'sha256':sha256(path),'status':'passed','budget':row['budget'],
                   'player':'FFplay with SDL dummy video driver and software renderer','human_continuous_viewing':False,
                   'played_frames':len(frame_ids),'elapsed_seconds':elapsed,'command':command,'player_log':str(log),
                   'source_export_alignment':{'compared_frames':count,'thumbnail_rgb_mae_mean':float(np.mean(errors)),'thumbnail_rgb_mae_max':max(errors),'tolerance':8}})
    print(f'Playback {budget}%: {count} frames, {elapsed:.2f}s, maximum alignment MAE {max(errors):.3f}',flush=True)
save_json(destination,{'status':'passed','reviewer_type':'agent','timestamp':datetime.now(timezone.utc).isoformat(),
    'method':'FFplay软件渲染器离屏按正常时钟完整播放三段，逐帧showinfo检查0到末帧和进程退出；逐帧比对导出图像与原片选帧的低分辨率RGB误差。主代理另查看三预算代表帧。未声称人类观看连续播放。',
    'media':audits,'visual_observation':'三种预算均保留轮胎/轮辋、手部工具操作和部分工作台画面；时间顺序递增，无选段倒放。5%片段更短更碎，不能完整保留维修动作和解释；视频无音轨，操作含义可能不完整。'})
