"""训练完成后的推理套件：示例推理、长音频阈值实验、检测时间线图、自录入口。

对基线模型 runs/best.pt 运行指导文档第 7 步与第 8 节（加分项）的全部推理内容，
结果保存为 JSON 与 PNG，供报告程序化引用。自录音频就位后重跑本脚本即可更新。

用法（在仓库根目录）:
    conda run -p D:/Anaconda3/envs/pytorch python -s speech/scripts/run_inference_suite.py
"""

import argparse
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "kws_hw"))

from features import SAMPLE_RATE, load_wav, wav_to_logmel  # noqa: E402
from model import DSConvNet  # noqa: E402

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=str,
                        default=str(ROOT / "kws_hw" / "runs" / "best.pt"))
    parser.add_argument("--data_dir", type=str,
                        default="E:/MultimediaCourseAssets/speech/data/processed")
    parser.add_argument("--sc_root", type=str,
                        default="E:/MultimediaCourseAssets/speech/data/speech_commands")
    parser.add_argument("--demo_wav", type=str,
                        default=str(ROOT / "kws_hw" / "demo_long.wav"))
    parser.add_argument("--my_recordings", type=str,
                        default=str(ROOT / "kws_hw" / "my_recordings"))
    parser.add_argument("--out_dir", type=str,
                        default=str(ROOT / "outputs" / "baseline"))
    parser.add_argument("--thresholds", type=float, nargs="+",
                        default=[0.5, 0.9, 0.99])
    return parser.parse_args()


def load_model(checkpoint, device):
    ckpt = torch.load(checkpoint, map_location=device, weights_only=False)
    model = DSConvNet(num_classes=len(ckpt["classes"]), width=ckpt["width"]).to(device)
    model.load_state_dict(ckpt["model"])
    model.eval()
    return ckpt, model


def infer_one(model, ckpt, wav_path, device, topk=3):
    """单条 1 秒级别音频的 top-k 预测，与教师 infer.py 同逻辑。"""
    feat = wav_to_logmel(load_wav(str(wav_path)))
    x = (feat - ckpt["mean"][:, None]) / ckpt["std"][:, None]
    x = torch.from_numpy(x).unsqueeze(0).unsqueeze(0).to(device)
    with torch.no_grad():
        probs = torch.softmax(model(x), dim=1)[0].cpu().numpy()
    idx = np.argsort(probs)[::-1][:topk]
    return {
        "file": Path(wav_path).name,
        "path": str(wav_path),
        "top": [{"class": ckpt["classes"][i], "prob": float(probs[i])} for i in idx],
    }


def detect_scores(model, ckpt, wav, device, target_idx, hop=0.25, batch_size=128):
    """与教师 detect.py 相同的滑动窗口打分，返回窗口中心时间与 yes 分数。"""
    mean, std = ckpt["mean"], ckpt["std"]
    win = SAMPLE_RATE
    hop_n = int(hop * SAMPLE_RATE)
    if len(wav) < win:
        wav = np.pad(wav, (0, win - len(wav)))
    starts = list(range(0, len(wav) - win + 1, hop_n))
    if starts[-1] + win < len(wav):
        starts.append(len(wav) - win)
    feats = np.stack([wav_to_logmel(wav[s:s + win]) for s in starts])
    x = (feats - mean[:, None]) / std[:, None]
    x = torch.from_numpy(x).astype(np.float32).unsqueeze(1)
    scores = []
    with torch.no_grad():
        for i in range(0, len(x), batch_size):
            logits = model(x[i:i + batch_size].to(device))
            scores.append(torch.softmax(logits, dim=1)[:, target_idx].cpu().numpy())
    scores = np.concatenate(scores)
    times = np.array(starts) / SAMPLE_RATE + 0.5
    return times, scores


def group_detections(times, scores, threshold):
    """连续超阈窗口合并为一组，每组取最高分——与教师 detect.py 一致。"""
    hits = np.where(scores >= threshold)[0]
    groups = []
    for i in hits:
        if groups and i - groups[-1][-1] <= 1:
            groups[-1].append(int(i))
        else:
            groups.append([int(i)])
    return [
        {"t": round(float(times[g[int(np.argmax(scores[g]))]]), 2),
         "score": round(float(np.max(scores[g])), 4)}
        for g in groups
    ]


def plot_timeline(times, scores, thresholds, detections_main, out_path, title):
    fig, ax = plt.subplots(figsize=(8, 3.6))
    ax.plot(times, scores, "o-", markersize=3, color="#1f77b4", label="yes 分数")
    colors = {0.5: "#2ca02c", 0.9: "#ff7f0e", 0.99: "#d62728"}
    for th in thresholds:
        ax.axhline(th, linestyle="--", linewidth=1,
                   color=colors.get(th, "gray"), label=f"阈值 {th:g}")
    for d in detections_main:
        ax.annotate(f"t={d['t']:.2f}s\n{d['score']:.3f}",
                    (d["t"], d["score"]), textcoords="offset points",
                    xytext=(0, 8), ha="center", fontsize=8, color="#d62728")
        ax.scatter([d["t"]], [d["score"]], marker="v", s=60, color="#d62728", zorder=5)
    ax.set_xlabel("时间 (s)")
    ax.set_ylabel("唤醒词 yes 的分数")
    ax.set_ylim(-0.03, 1.06)
    ax.set_title(title)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8, loc="center right")
    fig.tight_layout()
    fig.savefig(out_path, dpi=200)
    plt.close(fig)


def main():
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ckpt, model = load_model(args.checkpoint, device)
    classes = ckpt["classes"]
    target = "yes"
    target_idx = classes.index(target)
    results = {"checkpoint": str(args.checkpoint), "device": device.type, "target": target}

    # ---------- 1. 示例推理（指导文档 7.1） ----------
    demo_cases = {}
    sc_root = Path(args.sc_root)
    for word in ["yes", "stop"]:
        cands = sorted(sc_root.glob(f"{word}/*.wav"))
        if cands:
            demo_cases[word] = infer_one(model, ckpt, cands[0], device)
    results["infer_examples"] = demo_cases

    # ---------- 2. 长音频滑动窗口分数与阈值实验（指导文档 8.1 / 8.3） ----------
    wav = load_wav(args.demo_wav)
    times, scores = detect_scores(model, ckpt, wav, device, target_idx)
    results["demo_long"] = {
        "wav": str(args.demo_wav),
        "duration_s": round(len(wav) / SAMPLE_RATE, 2),
        "num_windows": int(len(times)),
    }
    threshold_results = {}
    for th in args.thresholds:
        dets = group_detections(times, scores, th)
        threshold_results[f"{th:g}"] = {"threshold": th,
                                        "num_detections": len(dets),
                                        "detections": dets}
    results["threshold_experiment"] = threshold_results

    plot_timeline(times, scores, args.thresholds,
                  threshold_results["0.9"]["detections"],
                  out_dir / "fig_detect_timeline.png",
                  "demo_long.wav 滑动窗口检测：静音→yes→静音→stop→静音→yes→静音")

    # ---------- 3. 自录音频入口（指导文档 7.2 / 8.2） ----------
    my_dir = Path(args.my_recordings)
    my_results = []
    if my_dir.exists():
        for wav_path in sorted(my_dir.glob("*.wav")):
            w = load_wav(str(wav_path))
            entry = {"file": wav_path.name, "duration_s": round(len(w) / SAMPLE_RATE, 2)}
            if len(w) < 3 * SAMPLE_RATE:
                entry["type"] = "keyword"
                entry["prediction"] = infer_one(model, ckpt, wav_path, device)
            else:
                entry["type"] = "long"
                t2, s2 = detect_scores(model, ckpt, w, device, target_idx)
                dets = group_detections(t2, s2, 0.9)
                entry["detections_at_0.9"] = dets
                plot_timeline(t2, s2, [0.5, 0.9, 0.99], dets,
                              out_dir / f"fig_detect_my_{wav_path.stem}.png",
                              f"自录长音频 {wav_path.name} 的滑动窗口检测")
            my_results.append(entry)
    results["my_recordings"] = my_results
    results["my_recordings_status"] = (
        "已处理自录音频" if my_results else
        "自录音频尚未提供：请将 16 kHz 单声道 wav 放入 speech/kws_hw/my_recordings/ 后重跑本脚本")

    with open(out_dir / "inference_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(json.dumps({k: results[k] for k in
                      ["infer_examples", "threshold_experiment", "my_recordings"]},
                     ensure_ascii=False, indent=2))
    print(f"\n[完成] 推理套件结果已保存到 {out_dir}")


if __name__ == "__main__":
    main()
