"""第 4 步：用训练好的模型识别自己的录音。

用法:
    python infer.py 我的录音.wav
    python infer.py 某个文件夹/

建议用手机录音，说一个关键词（例如 "yes"），保存为 16 kHz wav；
不是 16 kHz 也没关系，程序会自动重采样。
"""

import argparse
from pathlib import Path

import numpy as np
import torch

from features import load_and_featurize
from model import DSConvNet


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="+", help="wav 文件或文件夹")
    parser.add_argument("--checkpoint", type=str, default="runs/best.pt")
    parser.add_argument("--topk", type=int, default=3)
    return parser.parse_args()


def collect_wavs(inputs):
    wavs = []
    for item in inputs:
        path = Path(item)
        if path.is_dir():
            wavs.extend(sorted(path.glob("*.wav")))
        elif path.is_file():
            wavs.append(path)
        else:
            print(f"[跳过] 找不到 {path}")
    return wavs


def main():
    args = parse_args()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ckpt = torch.load(args.checkpoint, map_location=device, weights_only=False)
    classes = ckpt["classes"]
    mean, std = ckpt["mean"], ckpt["std"]

    model = DSConvNet(num_classes=len(classes), width=ckpt["width"]).to(device)
    model.load_state_dict(ckpt["model"])
    model.eval()

    wavs = collect_wavs(args.inputs)
    if not wavs:
        print("没有找到 wav 文件")
        return

    for wav_path in wavs:
        feat = load_and_featurize(str(wav_path))          # (40, 98)
        x = (feat - mean[:, None]) / std[:, None]
        x = torch.from_numpy(x).unsqueeze(0).unsqueeze(0).to(device)

        with torch.no_grad():
            probs = torch.softmax(model(x), dim=1)[0].cpu().numpy()

        topk = np.argsort(probs)[::-1][:args.topk]
        print(f"\n文件: {wav_path}")
        for rank, idx in enumerate(topk, 1):
            print(f"  {rank}. {classes[idx]:<8s} {probs[idx] * 100:6.2f}%")


if __name__ == "__main__":
    main()
