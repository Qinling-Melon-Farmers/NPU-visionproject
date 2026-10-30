"""Generate report figures with Chinese labels from saved experiment results.

Reads only existing outputs; no model inference.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "outputs" / "visual-20261023-fp32"
OUT = Path(__file__).resolve().parent / "figures_v2"
ASSET = Path("E:/MultimediaCourseAssets/vision")

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.dpi"] = 200
plt.rcParams["savefig.dpi"] = 200
plt.rcParams["font.size"] = 9


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save(fig, name: str):
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / name, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("saved", name)


def method_comparison():
    data = load_json(RUN / "image" / "results.json")
    methods = data["methods"]
    labels = {"gem": "GeM", "avg": "平均池化", "max": "最大池化"}
    colors = {"full": "#3B6EA8", "sparse": "#D98B4A"}
    fig, axes = plt.subplots(1, 2, figsize=(7.4, 2.9))
    for ax, key, title in zip(axes, ("mean_p_at_5", "map"), ("平均 P@5", "mAP")):
        x = np.arange(3)
        for offset, gallery in [(-0.18, "full"), (0.18, "sparse")]:
            vals = [
                next(m[key] for m in methods if m["gallery"] == gallery and m["method"] == name)
                for name in ("gem", "avg", "max")
            ]
            bars = ax.bar(x + offset, vals, width=0.34, color=colors[gallery],
                          label="主图库（6,800）" if gallery == "full" else "稀疏图库（800）")
            for bar, value in zip(bars, vals):
                ax.text(bar.get_x() + bar.get_width() / 2, value + 0.015, f"{value:.3f}",
                        ha="center", va="bottom", fontsize=7)
        ax.set_xticks(x)
        ax.set_xticklabels([labels[n] for n in ("gem", "avg", "max")])
        ax.set_ylim(0, 1.12)
        ax.set_ylabel("指标值")
        ax.grid(axis="y", linestyle=":", linewidth=0.5, alpha=0.6)
        ax.set_title(title, fontsize=10)
    axes[0].legend(frameon=False, fontsize=7.5, ncol=2, loc="upper center",
                   bbox_to_anchor=(0.5, -0.20))
    fig.tight_layout()
    save(fig, "fig01_methods.png")


def video_comparison():
    data = load_json(RUN / "video" / "results.json")
    metrics = data["metrics"]
    fig, ax = plt.subplots(figsize=(6.2, 2.6))
    x = np.arange(2)
    vals = [metrics["mAP"], metrics["without_cnn_mAP"]]
    bars = ax.bar(x, vals, width=0.45, color=["#3B6EA8", "#8C8C8C"])
    for bar, value in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 0.02, f"{value:.4f}",
                ha="center", va="bottom", fontsize=8)
    ax.set_xticks(x)
    ax.set_xticklabels(["完整 ViSiL", "去 CNN 对照"])
    ax.set_ylim(0, 1.15)
    ax.set_ylabel("mAP")
    ax.set_title("20 查询 / 90 候选：两种方法均为 1.0000", fontsize=10)
    ax.grid(axis="y", linestyle=":", linewidth=0.5, alpha=0.6)
    fig.tight_layout()
    save(fig, "fig06_video.png")


def summary_scores():
    data = np.load(RUN / "summary" / "prediction.npz", allow_pickle=False)
    picks = data["picks"]
    importance = data["importance"]
    centerness = data["centerness"]
    scores = data["scores"]
    result = load_json(RUN / "summary" / "results.json")
    selection = next(r for r in result["results"] if abs(r["budget"] - 0.15) < 1e-9)
    fig, ax = plt.subplots(figsize=(7.4, 2.8))
    ax.plot(picks, importance, label="重要性", color="#3B6EA8", linewidth=1.2)
    ax.plot(picks, centerness, label="中心度", color="#D98B4A", linewidth=1.2)
    ax.plot(picks, scores, label="NMS 后分数", color="#4C4C4C", linewidth=1.0, alpha=0.85)
    for seg in selection["segments"]:
        ax.axvspan(seg["first_frame"], seg["last_frame_inclusive"], color="#F2C14E", alpha=0.18, linewidth=0)
    ax.set_xlabel("原视频帧号")
    ax.set_ylabel("分数")
    ax.set_xlim(0, int(data["n_frames"]))
    ax.set_ylim(0, 1.02)
    ax.legend(frameon=False, fontsize=7.5, ncol=3, loc="upper center",
              bbox_to_anchor=(0.5, -0.22))
    ax.set_title("15% 预算下的重要性、中心度与所选片段（黄色区间）", fontsize=10)
    ax.grid(axis="y", linestyle=":", linewidth=0.5, alpha=0.6)
    fig.tight_layout()
    save(fig, "fig11_summary.png")


def heatmaps():
    data = np.load(RUN / "replay_video_matrices.npz", allow_pickle=False)
    for key, name, title in [
        ("relevant", "fig09_heat_relevant.png", "查询 EE-bNr36nyA_q1 与相关候选 q1_reencode"),
        ("distractor", "fig10_heat_distractor.png", "查询 EE-bNr36nyA_q1 与同源干扰 q2_reencode"),
    ]:
        matrix = data[f"{key}_matrix"]
        qs = data[f"{key}_query_seconds"]
        cs = data[f"{key}_candidate_seconds"]
        qid = str(data[f"{key}_query_id"])
        cid = str(data[f"{key}_candidate_id"])
        fig, ax = plt.subplots(figsize=(5.4, 4.4))
        im = ax.imshow(matrix, origin="lower", aspect="auto",
                       extent=[cs[0], cs[-1], qs[0], qs[-1]], cmap="viridis")
        ax.set_xlabel("候选视频时间（秒）")
        ax.set_ylabel("查询视频时间（秒）")
        ax.set_title(f"{title}\n{qid} → {cid}", fontsize=8.5)
        cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.03)
        cbar.set_label("区域匹配相似度", fontsize=8)
        fig.tight_layout()
        save(fig, name)


def coil_top5():
    per = list(csv.DictReader((RUN / "image" / "per_query.csv").open(encoding="utf-8-sig", newline="")))
    top = list(csv.DictReader((RUN / "image" / "top5.csv").open(encoding="utf-8-sig", newline="")))
    image_root = ASSET / "data" / "coil-100"

    def find_image(image_id: str) -> Path:
        matches = list(image_root.rglob(image_id))
        if not matches:
            raise FileNotFoundError(image_id)
        return matches[0]

    for gallery, label in [("full", "主图库"), ("sparse", "稀疏图库")]:
        rows = [r for r in per if r["gallery"] == gallery and r["method"] == "gem"]
        rows.sort(key=lambda r: (float(r["p_at_5"]), float(r["ap"]), r["query_id"]))
        for tag, row in [("best", rows[-1]), ("worst", rows[0])]:
            qid = row["query_id"]
            items = [r for r in top if r["gallery"] == gallery and r["method"] == "gem" and r["query_id"] == qid]
            items.sort(key=lambda r: int(r["rank"]))
            fig, axes = plt.subplots(1, 6, figsize=(8.6, 2.05))
            ids = [qid] + [r["candidate_id"] for r in items]
            scores = [None] + [float(r["score"]) for r in items]
            for ax, image_id, score in zip(axes, ids, scores):
                with plt.ioff():
                    image = plt.imread(find_image(image_id))
                ax.imshow(image)
                ax.axis("off")
                if score is None:
                    ax.set_title(f"查询\n{image_id}", fontsize=6.5)
                else:
                    ax.set_title(f"{image_id}\n相似度 {score:.4f}", fontsize=6.2)
            fig.suptitle(
                f"{label}{'最佳' if tag == 'best' else '最差'}查询 {qid}：P@5={float(row['p_at_5']):.2f}，AP={float(row['ap']):.4f}",
                fontsize=9,
            )
            fig.tight_layout(rect=(0, 0, 1, 0.92))
            save(fig, f"fig_top5_{gallery}_{tag}.png")


if __name__ == "__main__":
    method_comparison()
    video_comparison()
    summary_scores()
    heatmaps()
    coil_top5()
