"""数据准备核验：检查 data/processed 的形状、类别与划分，并写 evidence JSON。

核验点（对应指导文档 4.3 节）:
    - train/val/test 形状为 (21470, 40, 98) / (3096, 40, 98) / (3307, 40, 98)
    - 12 类、stats.npz 仅来自训练集（形状 (40,)）
    - test_files.txt 行数与测试集一致

输出:
    speech/outputs/data_summary.json   数据来源、MD5、规模与各类分布
    speech/outputs/environment.json    运行环境版本（从环境检查日志解析）
"""

import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path("E:/MultimediaCourseAssets/speech/data")
EXPECTED = {"train": 21470, "val": 3096, "test": 3307}


def md5_of(path, chunk=1 << 20):
    h = hashlib.md5()
    with open(path, "rb") as f:
        while True:
            block = f.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def main():
    processed = DATA_DIR / "processed"
    summary = {}

    archive = DATA_DIR / "speech_commands_v0.01.tar.gz"
    summary["source_url"] = ("http://download.tensorflow.org/data/"
                             "speech_commands_v0.01.tar.gz")
    summary["md5"] = md5_of(archive)
    summary["md5_expected"] = "3cd23799cb2bbdec517f1cc028f8d43c"
    summary["md5_ok"] = summary["md5"] == summary["md5_expected"]

    with open(processed / "meta.json", "r", encoding="utf-8") as f:
        meta = json.load(f)
    summary["classes"] = meta["classes"]
    assert len(meta["classes"]) == 12, "类别数不是 12"

    counts, failures = {}, []
    for split, expected_n in EXPECTED.items():
        x = np.load(processed / f"{split}_x.npy", mmap_mode="r")
        y = np.load(processed / f"{split}_y.npy")
        if x.shape != (expected_n, 40, 98):
            failures.append(f"{split}_x 形状 {x.shape} != ({expected_n}, 40, 98)")
        with open(processed / f"{split}_files.txt", "r", encoding="utf-8") as f:
            n_files = sum(1 for line in f if line.strip())
        if n_files != expected_n:
            failures.append(f"{split}_files.txt 行数 {n_files} != {expected_n}")
        counts[split] = {
            meta["classes"][i]: int((y == i).sum()) for i in range(12)
        }
        if sum(counts[split].values()) != expected_n:
            failures.append(f"{split} 类别计数之和 != {expected_n}")
    stats = np.load(processed / "stats.npz")
    if stats["mean"].shape != (40,) or stats["std"].shape != (40,):
        failures.append("stats.npz 形状异常（应各为 (40,)，仅训练集统计）")
    summary["counts"] = counts
    summary["num_train"], summary["num_val"], summary["num_test"] = (
        EXPECTED["train"], EXPECTED["val"], EXPECTED["test"])
    summary["feature"] = meta["feature"]
    summary["failures"] = failures

    out = ROOT / "outputs"
    out.mkdir(exist_ok=True)
    with open(out / "data_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # 环境版本：从环境检查日志解析最后一段 JSON
    log = (ROOT / "logs" / "environment-check-20261031.txt").read_text(
        encoding="utf-8", errors="replace")
    blocks = re.findall(r"\{.*?\}", log, flags=re.S)
    env = json.loads(blocks[-1]) if blocks else {}
    keep = ["python", "executable", "numpy", "scipy", "soundfile", "sklearn",
            "matplotlib", "tqdm", "torch", "torch.version.cuda",
            "cuda.is_available", "gpu"]
    with open(out / "environment.json", "w", encoding="utf-8") as f:
        json.dump({k: env.get(k) for k in keep}, f, ensure_ascii=False, indent=2)

    print(json.dumps({k: summary[k] for k in
                      ["md5_ok", "num_train", "num_val", "num_test", "failures"]},
                     ensure_ascii=False, indent=2))
    if failures or not summary["md5_ok"]:
        print("[失败] 数据核验未通过")
        sys.exit(1)
    print("[OK] 数据核验通过，evidence 已写入 outputs/")


if __name__ == "__main__":
    main()
