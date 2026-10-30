"""第 3 步：在测试集上评估模型。

运行:
    python evaluate.py

会输出:
    - 测试集总体准确率
    - 每个类别的 precision / recall / F1（打印并保存 txt）
    - 混淆矩阵 confusion_matrix.png
    - 把 "yes" 当作唤醒词时的 DET 曲线 det_curve.png
    - 分数分布 score_hist.png
    - 所有指标 metrics.json
"""

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch
from sklearn.metrics import (
    accuracy_score,
    auc,
    classification_report,
    confusion_matrix,
    roc_curve,
)
from torch.utils.data import DataLoader
from tqdm import tqdm

from model import DSConvNet
from train import KWSData


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=str, default="runs/best.pt")
    parser.add_argument("--data_dir", type=str, default="data/processed")
    parser.add_argument("--save_dir", type=str, default="runs")
    parser.add_argument("--batch_size", type=int, default=256)
    parser.add_argument("--target", type=str, default="yes",
                        help="把哪个类别当作唤醒词（默认 yes）")
    return parser.parse_args()


@torch.no_grad()
def predict(model, loader, device):
    model.eval()
    all_probs, all_labels = [], []
    for x, y in tqdm(loader, desc="      test "):
        logits = model(x.to(device, non_blocking=True))
        probs = torch.softmax(logits, dim=1).cpu().numpy()
        all_probs.append(probs)
        all_labels.append(y.numpy())
    return np.concatenate(all_probs), np.concatenate(all_labels)


def plot_confusion_matrix(cm, classes, save_path):
    fig, ax = plt.subplots(figsize=(8, 7))
    im = ax.imshow(cm, interpolation="nearest", cmap="Blues")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    ax.set_xticks(np.arange(len(classes)))
    ax.set_yticks(np.arange(len(classes)))
    ax.set_xticklabels(classes, rotation=45, ha="right")
    ax.set_yticklabels(classes)
    ax.set_xlabel("Predicted label")
    ax.set_ylabel("True label")
    ax.set_title("Confusion Matrix (test set)")

    threshold = cm.max() / 2.0
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            ax.text(j, i, str(cm[i, j]), ha="center", va="center",
                    color="white" if cm[i, j] > threshold else "black",
                    fontsize=8)
    fig.tight_layout()
    fig.savefig(save_path, dpi=150)
    plt.close(fig)


def frr_at_far(fpr, frr, far):
    """在 FAR <= far 的条件下，取最小的 FRR。"""
    idx = np.searchsorted(fpr, far, side="right") - 1
    idx = int(np.clip(idx, 0, len(frr) - 1))
    return float(frr[idx]), float(fpr[idx])


def plot_det(fpr, frr, far_points, eer, save_path):
    fig, ax = plt.subplots(figsize=(5.5, 5))
    ax.loglog(np.clip(fpr, 1e-5, 1), np.clip(frr, 1e-5, 1), "b-", label="DET")
    ax.loglog([1e-5, 1], [1e-5, 1], "k--", linewidth=0.8, label="EER line")
    ax.plot([eer], [eer], "ro", label=f"EER = {eer * 100:.2f}%")
    for far, (frr_p, far_p) in far_points.items():
        ax.plot([far_p], [frr_p], "g^")
        ax.annotate(f"FAR {far * 100:g}% -> FRR {frr_p * 100:.2f}%",
                    (far_p, frr_p), textcoords="offset points",
                    xytext=(6, 6), fontsize=8)
    ax.set_xlabel("False Acceptance Rate (FAR)")
    ax.set_ylabel("False Rejection Rate (FRR)")
    ax.set_title("Wake-word detection DET curve")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(save_path, dpi=150)
    plt.close(fig)


def plot_scores(scores, is_pos, save_path):
    fig, ax = plt.subplots(figsize=(6, 4))
    bins = np.linspace(0, 1, 50)
    ax.hist(scores[is_pos], bins=bins, alpha=0.6, density=True, label="Wake word")
    ax.hist(scores[~is_pos], bins=bins, alpha=0.6, density=True, label="Others")
    ax.set_xlabel("Score of target keyword")
    ax.set_ylabel("Density")
    ax.set_title("Score distribution on test set")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(save_path, dpi=150)
    plt.close(fig)


def main():
    args = parse_args()
    save_dir = Path(args.save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ckpt = torch.load(args.checkpoint, map_location=device, weights_only=False)
    classes = ckpt["classes"]
    mean, std = ckpt["mean"], ckpt["std"]

    if args.target not in classes:
        raise ValueError(f"target={args.target} 不在类别表 {classes} 里")

    model = DSConvNet(num_classes=len(classes), width=ckpt["width"]).to(device)
    model.load_state_dict(ckpt["model"])

    test_set = KWSData(args.data_dir, "test", mean, std, augment=False)
    test_loader = DataLoader(test_set, batch_size=args.batch_size, shuffle=False)
    print(f"[测试集] {len(test_set)} 条，模型来自 epoch {ckpt['epoch']} "
          f"(val_acc={ckpt['val_acc'] * 100:.2f}%)")

    probs, labels = predict(model, test_loader, device)
    preds = probs.argmax(axis=1)
    acc = accuracy_score(labels, preds)

    print("\n" + "=" * 60)
    print(f"测试集准确率: {acc * 100:.2f}%")
    print("=" * 60)

    report = classification_report(
        labels, preds, target_names=classes, digits=4, zero_division=0
    )
    print(report)
    with open(save_dir / "classification_report.txt", "w", encoding="utf-8") as f:
        f.write(report)

    cm = confusion_matrix(labels, preds)
    plot_confusion_matrix(cm, classes, save_dir / "confusion_matrix.png")

    # 保存分错的样本，方便挑几条出来听，写错误分析
    with open(Path(args.data_dir) / "test_files.txt", "r", encoding="utf-8") as f:
        test_files = [line.split("\t")[0] for line in f if line.strip()]
    if len(test_files) != len(labels):
        print(f"[警告] test_files.txt 行数与测试集不一致，错误列表改用序号")
        test_files = [f"index_{i}" for i in range(len(labels))]
    error_idx = np.where(preds != labels)[0]
    error_idx = error_idx[np.argsort(-probs[error_idx, preds[error_idx]])]
    with open(save_dir / "misclassified.txt", "w", encoding="utf-8") as f:
        f.write("file\ttrue\tpred\tprob_of_pred\n")
        for i in error_idx:
            f.write(f"{test_files[i]}\t{classes[labels[i]]}\t"
                    f"{classes[preds[i]]}\t{probs[i, preds[i]]:.4f}\n")
    print(f"错误样本 {len(error_idx)} 条，已保存到 {save_dir / 'misclassified.txt'}")

    # ---------- 唤醒词检测指标 ----------
    target_idx = classes.index(args.target)
    scores = probs[:, target_idx]
    is_pos = labels == target_idx
    fpr, tpr, _ = roc_curve(is_pos, scores)
    frr = 1.0 - tpr
    roc_auc = auc(fpr, tpr)
    eer = float(fpr[np.argmin(np.abs(frr - fpr))])

    far_points = {}
    for far in [1e-2, 1e-3]:
        frr_p, far_p = frr_at_far(fpr, frr, far)
        far_points[far] = (frr_p, far_p)

    print(f"唤醒词 '{args.target}' 检测指标（测试集，{int(is_pos.sum())} 条正样本 / "
          f"{int((~is_pos).sum())} 条负样本）:")
    print(f"  ROC-AUC = {roc_auc:.4f}")
    print(f"  EER     = {eer * 100:.2f}%")
    for far, (frr_p, far_p) in far_points.items():
        print(f"  FAR={far * 100:g}% 时 FRR = {frr_p * 100:.2f}%  (实际 FAR={far_p * 100:.2f}%)")

    plot_det(fpr, frr, far_points, eer, save_dir / "det_curve.png")
    plot_scores(scores, is_pos, save_dir / "score_hist.png")

    metrics = {
        "accuracy": float(acc),
        "num_errors": int((preds != labels).sum()),
        "target": args.target,
        "roc_auc": float(roc_auc),
        "eer": eer,
        "num_positive": int(is_pos.sum()),
        "num_negative": int((~is_pos).sum()),
        "frr_at_far": {
            f"{far:g}": {"frr": frr_p, "far_actual": far_p}
            for far, (frr_p, far_p) in far_points.items()
        },
        "checkpoint_epoch": int(ckpt["epoch"]),
        "checkpoint_val_acc": float(ckpt["val_acc"]),
    }
    with open(save_dir / "metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)

    print(f"\n[完成] 结果图已保存到 {save_dir}/")


if __name__ == "__main__":
    main()
