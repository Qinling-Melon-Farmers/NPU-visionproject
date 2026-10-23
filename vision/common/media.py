"""RGB video decoding through FFmpeg bundled in the active Conda prefix."""
from pathlib import Path
import json
import math
import subprocess
import sys
import tempfile
import numpy as np
import cv2

def _tool(name):
    executable=Path(sys.prefix)/'Library'/'bin'/(name+'.exe')
    if not executable.is_file():raise FileNotFoundError(f'Active Conda FFmpeg tool missing: {executable}')
    return str(executable)

def _ratio(value):
    try:
        a,b=str(value).split('/');return float(a)/float(b)
    except (ValueError,ZeroDivisionError):return 0.0

def probe_video(path):
    command=[_tool('ffprobe'),'-v','error','-select_streams','v:0','-show_entries',
             'stream=width,height,avg_frame_rate,r_frame_rate,nb_frames,duration:format=duration','-of','json',str(path)]
    process=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False)
    if process.returncode:raise RuntimeError(f'ffprobe failed ({process.returncode}): {process.stderr.decode("utf-8",errors="replace")}')
    info=json.loads(process.stdout);streams=info.get('streams',[])
    if not streams:raise ValueError(f'No video stream: {path}')
    stream=streams[0];fps=_ratio(stream.get('avg_frame_rate','0/0')) or _ratio(stream.get('r_frame_rate','0/0'))
    if not fps or not math.isfinite(fps):raise ValueError(f'Invalid source FPS: {path}')
    count=stream.get('nb_frames')
    if count in (None,'N/A'):
        counter=subprocess.run([_tool('ffprobe'),'-v','error','-count_frames','-select_streams','v:0',
            '-show_entries','stream=nb_read_frames','-of','json',str(path)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        if counter.returncode:raise RuntimeError(counter.stderr.decode('utf-8',errors='replace'))
        count=json.loads(counter.stdout)['streams'][0]['nb_read_frames']
    duration=stream.get('duration',info.get('format',{}).get('duration'))
    return dict(width=int(stream['width']),height=int(stream['height']),fps=fps,
                frame_count=int(count),duration=float(duration) if duration not in (None,'N/A') else int(count)/fps)

def _frames(path,info,filters=None,seconds=None):
    command=[_tool('ffmpeg'),'-nostdin','-v','error','-i',str(path),'-map','0:v:0']
    if seconds is not None:command+=['-ss',str(seconds),'-frames:v','1']
    if filters:command+=['-vf',filters]
    command+=['-vsync','0','-f','rawvideo','-pix_fmt','rgb24','pipe:1']
    frame_bytes=info['width']*info['height']*3
    with tempfile.TemporaryFile() as errors:
        process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=errors)
        completed=False
        try:
            while True:
                pieces=[];remaining=frame_bytes
                while remaining:
                    piece=process.stdout.read(remaining)
                    if not piece:break
                    pieces.append(piece);remaining-=len(piece)
                if remaining==frame_bytes:break
                if remaining:raise RuntimeError(f'FFmpeg produced truncated RGB frame: {path}')
                yield np.frombuffer(b''.join(pieces),dtype=np.uint8).reshape(info['height'],info['width'],3).copy()
            code=process.wait();completed=True
            if code:
                errors.seek(0);message=errors.read().decode('utf-8',errors='replace')
                raise RuntimeError(f'ffmpeg decode failed ({code}): {message}')
        finally:
            process.stdout.close()
            if not completed:
                if process.poll() is None:process.terminate()
                process.wait()

def iter_frames(path):
    """Yield every decoded RGB frame in order, without frame duplication."""
    yield from _frames(path,probe_video(path))

def read_frame(path,seconds):
    """Decode the first source frame at/after a nonnegative time in seconds."""
    if not math.isfinite(seconds) or seconds<0:raise ValueError('seconds must be finite and nonnegative')
    frames=list(_frames(path,probe_video(path),seconds=seconds))
    if not frames:raise ValueError(f'No video frame at {seconds}s: {path}')
    return frames[0]

def sample_frames(path,fps=1,cc_size=224,rs_size=256):
    """Return only selected RGB frames using the author's integer frame stride.

    FFmpeg selects indices 0, round(sourcefps/requestfps), ... in one process;
    unsampled frames are never transferred to Python. Resize and crop exactly
    follow the author's cv2 INTER_CUBIC and integer center-crop implementation.
    """
    if not math.isfinite(fps) or fps<=0:raise ValueError('Requested FPS must be positive')
    info=probe_video(path);source_fps=info['fps']
    if source_fps>144:source_fps=25
    step=round(source_fps/fps)
    if step<1:raise ValueError('Requested FPS produces a zero author sampling stride')
    cv2.setNumThreads(1)
    frames=[]
    for frame in _frames(path,info,filters=f'select=not(mod(n\\,{step}))'):
        if rs_size is not None:
            ratio=rs_size/min(frame.shape[:2])
            frame=cv2.resize(frame,dsize=(0,0),fx=ratio,fy=ratio,interpolation=cv2.INTER_CUBIC)
        if cc_size is not None:
            top=int(max(0,(frame.shape[0]-cc_size)/2));left=int(max(0,(frame.shape[1]-cc_size)/2))
            frame=frame[top:top+cc_size,left:left+cc_size,:]
        frames.append(frame)
    return np.array(frames)
