"""自录原始录音转码：my_recordings_raw/ 的 m4a/mp3 等 → my_recordings/ 的 16 kHz 单声道 wav。

文件名按根目录《自录音频准备清单.md》的映射表改为规范名；已在 my_recordings/ 里的
同名 wav 会被覆盖。需要 ffmpeg：优先 PATH，其次回退到 multimedia-vision 环境自带的
ffmpeg（本机未全局安装 ffmpeg，转码只借用其二进制，不改动任何环境）。

用法（在仓库根目录）:
    D:/Anaconda3/envs/pytorch/python.exe -s speech/scripts/convert_recordings.py
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "kws_hw" / "my_recordings_raw"
OUT = ROOT / "kws_hw" / "my_recordings"

# 原始文件名（不含扩展名）→ 规范 wav 名
NAME_MAP = {
    "yes": "kw_yes_01", "no": "kw_no_01", "up": "kw_up_01",
    "down": "kw_down_01", "left": "kw_left_01", "right": "kw_right_01",
    "on": "kw_on_01", "off": "kw_off_01", "stop": "kw_stop_01",
    "go": "kw_go_01",
    "hello": "kw_other_hello_01", "house": "kw_other_house_01",
    "shi": "kw_zh_shi_01", "ting": "kw_zh_ting_01",
    "demo": "long_demo_01",
}

FFMPEG_FALLBACK = "E:/MultimediaCourseAssets/envs/multimedia-vision/Library/bin/ffmpeg.exe"


def find_ffmpeg():
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    if Path(FFMPEG_FALLBACK).is_file():
        return FFMPEG_FALLBACK
    raise SystemExit("找不到 ffmpeg：请安装或确认 FFMPEG_FALLBACK 路径存在")


def main():
    if not RAW.is_dir():
        raise SystemExit(f"原始录音目录不存在：{RAW}")
    OUT.mkdir(parents=True, exist_ok=True)
    ffmpeg = find_ffmpeg()
    done = 0
    for src in sorted(RAW.iterdir()):
        if src.suffix.lower() not in (".m4a", ".mp3", ".aac", ".ogg", ".flac"):
            continue
        stem = src.stem.lower()
        name = NAME_MAP.get(stem)
        if name is None:
            print(f"[跳过] {src.name} 不在映射表中（按清单命名后重跑）")
            continue
        dst = OUT / f"{name}.wav"
        subprocess.run(
            [ffmpeg, "-y", "-loglevel", "error", "-i", str(src),
             "-ar", "16000", "-ac", "1", "-sample_fmt", "s16", str(dst)],
            check=True)
        print(f"[转码] {src.name} -> {dst.name}")
        done += 1
    print(f"[完成] 共转码 {done} 个文件 -> {OUT}")


if __name__ == "__main__":
    sys.exit(main())
