"""错误分析素材：从 misclassified.txt 取 top 置信错误，生成波形 + log-Mel 对照图。

用法（在仓库根目录，需先完成基线训练与评估）:
    conda run -p D:/Anaconda3/envs/pytorch python -s speech/scripts/make_error_analysis.py
"""

import argparse
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "kws_hw"))

from features import SAMPLE_RATE, load_wav, wav_to_logmel  # noqa: E402

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs_dir", type=str,
                        default=str(ROOT / "kws_hw" / "runs"))
    parser.add_argument("--sc_root", type=str,
                        default="E:/MultimediaCourseAssets/speech/data/speech_commands")
    parser.add_argument("--out_dir", type=str,
                        default=str(ROOT / "outputs" / "baseline"))
    parser.add_argument("--top_n", type=int, default=4)
    return parser.parse_args()


def feature_example(sc_root, out_dir):
    """图 1：一条 yes 测试样本的波形 + log-Mel 特征对照。"""
    wav_path = sorted(sc_root.glob("yes/*.wav"))[0]
    wav = load_wav(str(wav_path))
    feat = wav_to_logmel(wav)
    t = np.arange(len(wav)) / SAMPLE_RATE

    fig, axes = plt.subplots(2, 1, figsize=(9, 4.6), sharex=True)
    axes[0].plot(t, wav, linewidth=0.4, color="#1f77b4")
    axes[0].set_ylabel("幅度")
    axes[0].set_title(f"波形：{wav_path.name}", fontsize=10, loc="left")
    im = axes[1].imshow(feat, aspect="auto", origin="lower",
                        extent=[0, 1, 0, 40], cmap="viridis")
    axes[1].set_ylabel("Mel 频带")
    axes[1].set_xlabel("时间 (s)")
    axes[1].set_title("log-Mel 特征：40 频带 × 98 帧", fontsize=10, loc="left")
    fig.colorbar(im, ax=axes[1], fraction=0.03, pad=0.02)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_feature_example.png", dpi=200)
    plt.close(fig)


def main():
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    sc_root = Path(args.sc_root)

    feature_example(sc_root, out_dir)

    cases = []
    with open(Path(args.runs_dir) / "misclassified.txt", "r", encoding="utf-8") as f:
        next(f)
        for line in f:
            name, true_label, pred, prob = line.strip().split("\t")
            cases.append({"file": name, "true": true_label,
                          "pred": pred, "prob": float(prob)})
            if len(cases) >= args.top_n:
                break

    n = len(cases)
    fig, axes = plt.subplots(n, 2, figsize=(10, 2.2 * n))
    if n == 1:
        axes = axes[None, :]
    for row, case in enumerate(cases):
        wav = load_wav(str(sc_root / case["file"]))
        feat = wav_to_logmel(wav)

        t = np.arange(len(wav)) / SAMPLE_RATE
        axes[row, 0].plot(t, wav, linewidth=0.4, color="#1f77b4")
        axes[row, 0].set_xlim(0, 1.0)
        axes[row, 0].set_ylabel("幅度")
        axes[row, 0].set_title(f"真实: {case['true']}   预测: {case['pred']}   "
                               f"p(预测)={case['prob']:.4f}   [{case['file']}]",
                               fontsize=9, loc="left")

        im = axes[row, 1].imshow(feat, aspect="auto", origin="lower",
                                 extent=[0, 1, 0, 40], cmap="viridis")
        axes[row, 1].set_ylabel("Mel 频带")
        if row == n - 1:
            axes[row, 0].set_xlabel("时间 (s)")
            axes[row, 1].set_xlabel("时间 (s)")
        fig.colorbar(im, ax=axes[row, 1], fraction=0.03, pad=0.02)

    fig.suptitle("测试集最高置信错误样本：波形与 log-Mel 特征对照", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(out_dir / "fig_error_analysis.png", dpi=200)
    plt.close(fig)

    with open(out_dir / "error_cases.json", "w", encoding="utf-8") as f:
        json.dump({"top_cases": cases, "total_shown": n},
                  f, ensure_ascii=False, indent=2)
    print(f"[完成] 已生成 {out_dir / 'fig_error_analysis.png'}，共 {n} 条案例")
    for c in cases:
        print(f"  {c['file']}: {c['true']} -> {c['pred']} (p={c['prob']:.4f})")


if __name__ == "__main__":
    main()
