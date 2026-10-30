"""消融实验汇总：读取各 run 的 metrics.json / history.json / classification_report.txt，
生成对比 JSON（含参数量、训练用时、准确率、宏 F1、EER），供报告直接引用。

用法（在仓库根目录，需先完成四个训练与评估）:
    conda run -p D:/Anaconda3/envs/pytorch python -s speech/scripts/summarize_ablation.py
"""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "kws_hw"))

from model import DSConvNet, count_parameters  # noqa: E402

RUN_LABELS = {
    "runs": "基线：40 epoch + 增强（width 32）",
    "runs_20": "少训练：20 epoch + 增强（width 32）",
    "runs_noaug": "关闭增强：40 epoch 无增强（width 32）",
    "runs_w48": "加宽模型：40 epoch + 增强（width 48）",
}


def parse_macro_f1(report_path):
    """从 classification_report.txt 读 macro avg 行的 f1-score。"""
    try:
        text = Path(report_path).read_text(encoding="utf-8")
    except OSError:
        return None
    m = re.search(r"macro avg\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)", text)
    return float(m.group(3)) if m else None


def parse_train_minutes(log_path):
    """从训练控制台日志读“用时 X.X 分钟”。"""
    try:
        text = Path(log_path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    m = re.search(r"用时\s+([0-9.]+)\s*分钟", text)
    return float(m.group(1)) if m else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--kws_root", type=str,
                        default=str(ROOT / "kws_hw"))
    parser.add_argument("--logs_dir", type=str, default=str(ROOT / "logs"))
    parser.add_argument("--out", type=str,
                        default=str(ROOT / "outputs" / "ablation_summary.json"))
    args = parser.parse_args()
    kws_root = Path(args.kws_root)

    rows = []
    for run_id, label in RUN_LABELS.items():
        run_dir = kws_root / run_id
        metrics_path = run_dir / "metrics.json"
        if not metrics_path.exists():
            rows.append({"run": run_id, "label": label, "status": "missing"})
            continue
        with open(metrics_path, "r", encoding="utf-8") as f:
            metrics = json.load(f)
        with open(run_dir / "history.json", "r", encoding="utf-8") as f:
            history = json.load(f)
        width = 48 if run_id == "runs_w48" else 32
        params_k = count_parameters(DSConvNet(num_classes=12, width=width)) / 1000
        rows.append({
            "run": run_id,
            "label": label,
            "status": "ok",
            "params_k": round(params_k, 2),
            "epochs": len(history["train_loss"]),
            "best_val_acc": round(max(history["val_acc"]) * 100, 2),
            "test_accuracy": round(metrics["accuracy"] * 100, 2),
            "macro_f1": parse_macro_f1(run_dir / "classification_report.txt"),
            "eer_percent": round(metrics["eer"] * 100, 2),
            "roc_auc": round(metrics["roc_auc"], 4),
            "frr_at_far1": round(
                metrics["frr_at_far"]["0.01"]["frr"] * 100, 2),
            "checkpoint_epoch": metrics["checkpoint_epoch"],
            "train_minutes": parse_train_minutes(
                Path(args.logs_dir) / f"train-{run_id}.log"),
        })

    summary = {
        "protocol": "同一测试集(3307 条)、同一 evaluate.py、同一划分；唯一差异为命令行参数",
        "commands": {
            "runs": "python -s train.py  (默认 40 epoch, 增强, width 32)",
            "runs_20": "python -s train.py --epochs 20 --save_dir runs_20",
            "runs_noaug": "python -s train.py --no_augment --save_dir runs_noaug",
            "runs_w48": "python -s train.py --width 48 --save_dir runs_w48",
        },
        "rows": rows,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(json.dumps(rows, ensure_ascii=False, indent=2))
    print(f"\n[完成] 消融汇总已保存到 {out}")


if __name__ == "__main__":
    main()
