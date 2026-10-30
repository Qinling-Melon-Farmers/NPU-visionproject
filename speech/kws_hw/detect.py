"""加分项：在一段长录音里滑动窗口检测唤醒词。

用法:
    python detect.py 长录音.wav --target yes --threshold 0.9

原理: 每 0.25 秒取一个 1 秒窗口，送入模型打分；
      分数连续超过阈值的片段里只保留一个最高分，作为一次“唤醒”。
"""

import argparse
from pathlib import Path

import numpy as np
import torch

from features import SAMPLE_RATE, load_wav, wav_to_logmel
from model import DSConvNet


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("wav", type=str, help="长录音 wav")
    parser.add_argument("--checkpoint", type=str, default="runs/best.pt")
    parser.add_argument("--target", type=str, default="yes")
    parser.add_argument("--threshold", type=float, default=0.9)
    parser.add_argument("--hop", type=float, default=0.25, help="窗口滑动步长（秒）")
    parser.add_argument("--batch_size", type=int, default=128)
    return parser.parse_args()


def main():
    args = parse_args()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ckpt = torch.load(args.checkpoint, map_location=device, weights_only=False)
    classes = ckpt["classes"]
    mean, std = ckpt["mean"], ckpt["std"]
    target_idx = classes.index(args.target)

    model = DSConvNet(num_classes=len(classes), width=ckpt["width"]).to(device)
    model.load_state_dict(ckpt["model"])
    model.eval()

    wav = load_wav(args.wav)
    win = SAMPLE_RATE                      # 1 秒窗口
    hop = int(args.hop * SAMPLE_RATE)
    if len(wav) < win:
        wav = np.pad(wav, (0, win - len(wav)))

    starts = list(range(0, len(wav) - win + 1, hop))
    if starts[-1] + win < len(wav):        # 补上最后一个不完整的窗口
        starts.append(len(wav) - win)

    feats = np.stack([wav_to_logmel(wav[s:s + win]) for s in starts])
    x = (feats - mean[:, None]) / std[:, None]
    x = torch.from_numpy(x).unsqueeze(1)

    all_scores = []
    with torch.no_grad():
        for i in range(0, len(x), args.batch_size):
            logits = model(x[i:i + args.batch_size].to(device))
            probs = torch.softmax(logits, dim=1)
            all_scores.append(probs[:, target_idx].cpu().numpy())
    scores = np.concatenate(all_scores)

    # 连续超过阈值的窗口归为一组，每组只保留最高分
    hits = np.where(scores >= args.threshold)[0]
    groups = []
    for idx in hits:
        if groups and idx - groups[-1][-1] <= 1:
            groups[-1].append(idx)
        else:
            groups.append([idx])

    detections = []
    for group in groups:
        best = group[int(np.argmax(scores[group]))]
        detections.append((starts[best] / SAMPLE_RATE + 0.5, float(scores[best])))

    print(f"目标唤醒词: '{args.target}'   阈值: {args.threshold}")
    print(f"音频长度: {len(wav) / SAMPLE_RATE:.2f} s   窗口数: {len(starts)}")
    if detections:
        print(f"检测到 {len(detections)} 次:")
        for t, score in detections:
            print(f"  t = {t:6.2f} s   score = {score:.4f}")
    else:
        best = int(np.argmax(scores))
        print("没有检测到。最高分窗口: "
              f"t = {starts[best] / SAMPLE_RATE + 0.5:.2f} s, score = {scores[best]:.4f}")
        print("可以把 --threshold 调低一点再试。")


if __name__ == "__main__":
    main()
