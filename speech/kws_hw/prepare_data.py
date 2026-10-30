"""第 1 步：下载数据、划分数据集、提取 log-Mel 特征。

运行:
    python prepare_data.py

默认会做这些事:
    1. 下载 Speech Commands v0.01（约 1.5 GB）
    2. 解压到 data/speech_commands/
    3. 选 10 个关键词 + unknown + silence 共 12 类
    4. 按官方 validation_list.txt / testing_list.txt 划分 train/val/test
    5. 提取 40x98 的 log-Mel 特征，保存成 .npy

跑完后 data/processed/ 里会有:
    train_x.npy  train_y.npy
    val_x.npy    val_y.npy
    test_x.npy   test_y.npy
    stats.npz    meta.json
"""

import argparse
import json
import multiprocessing as mp
import os
import random
import socket
import tarfile
import time
import urllib.request
from pathlib import Path

import numpy as np
import soundfile as sf
from tqdm import tqdm

from features import CLIP_SAMPLES, load_and_featurize, wav_to_logmel

DATA_URL = "http://download.tensorflow.org/data/speech_commands_v0.01.tar.gz"
ARCHIVE_NAME = "speech_commands_v0.01.tar.gz"

# 10 个关键词（顺序就是类别编号 0~9）
KEYWORDS = ["yes", "no", "up", "down", "left", "right", "on", "off", "stop", "go"]
CLASSES = KEYWORDS + ["unknown", "silence"]

# unknown 类从其余 20 个单词里抽样，三个集合各抽多少个
NUM_UNKNOWN = {"train": 2500, "val": 400, "test": 500}

SILENCE_FILES = {"train": 3, "val": 1, "test": 2}  # 6 个噪声文件怎么分


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_dir", type=str, default="data")
    parser.add_argument("--skip_download", action="store_true",
                        help="已经手动下载好压缩包时加上这个参数")
    parser.add_argument("--workers", type=int,
                        default=min(8, os.cpu_count() or 4),
                        help="特征提取的进程数")
    return parser.parse_args()


def download_with_progress(url, dst):
    """下载文件，支持 http_proxy / https_proxy 环境变量。"""
    if dst.exists() and dst.stat().st_size > 1_000_000_000:
        print(f"[跳过下载] {dst} 已存在")
        return

    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(".part")
    if tmp.exists():
        tmp.unlink()

    print(f"[下载] {url}")
    print("       文件约 1.5 GB，请保持网络畅通……")
    socket.setdefaulttimeout(60)
    last_print = [0.0]

    def report(blocks, block_size, total_size):
        downloaded = blocks * block_size
        now = time.time()
        if now - last_print[0] > 2 or downloaded >= total_size:
            last_print[0] = now
            if total_size > 0:
                pct = min(100.0, downloaded * 100.0 / total_size)
                print(f"\r       已下载 {downloaded / 1e6:8.1f} MB / "
                      f"{total_size / 1e6:.1f} MB ({pct:5.1f}%)", end="")
            else:
                print(f"\r       已下载 {downloaded / 1e6:.1f} MB", end="")

    urllib.request.urlretrieve(url, tmp, reporthook=report)
    print()
    tmp.rename(dst)
    print(f"[下载完成] {dst}")


def extract_archive(archive, out_dir):
    """解压到 out_dir；已经解压过就跳过。"""
    if (out_dir / "validation_list.txt").exists():
        print(f"[跳过解压] {out_dir} 已存在")
        return

    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"[解压] {archive} -> {out_dir}")
    with tarfile.open(archive, "r:gz") as tar:
        try:
            tar.extractall(out_dir, filter="data")   # Python 3.12+
        except TypeError:
            tar.extractall(out_dir)                  # Python 3.10/3.11
    print("[解压完成]")


def read_split_list(path):
    with open(path, "r", encoding="utf-8") as f:
        return {line.strip() for line in f if line.strip()}


def rel_path(word, wav_path):
    return f"{word}/{wav_path.name}"


def collect_keywords(root, val_list, test_list):
    """收集 10 个关键词，并按官方列表划分。"""
    items = {"train": [], "val": [], "test": []}
    for label, word in enumerate(KEYWORDS):
        for wav_path in sorted((root / word).glob("*.wav")):
            rel = rel_path(word, wav_path)
            if rel in test_list:
                split = "test"
            elif rel in val_list:
                split = "val"
            else:
                split = "train"
            items[split].append((wav_path, label))
    return items


def collect_unknown(root, val_list, test_list):
    """从另外 20 个单词里抽样作为 unknown 类（标签 10）。"""
    all_dirs = sorted(p.name for p in root.iterdir()
                      if p.is_dir() and not p.name.startswith("_"))
    extra_words = [w for w in all_dirs if w not in KEYWORDS]

    pools = {"train": [], "val": [], "test": []}
    for word in extra_words:
        for wav_path in sorted((root / word).glob("*.wav")):
            rel = rel_path(word, wav_path)
            if rel in test_list:
                split = "test"
            elif rel in val_list:
                split = "val"
            else:
                split = "train"
            pools[split].append((wav_path, 10))

    items = {}
    for i, split in enumerate(["train", "val", "test"]):
        rng = random.Random(2024 + i)   # 固定随机种子，结果可复现
        pool = pools[split]
        rng.shuffle(pool)
        n = min(NUM_UNKNOWN[split], len(pool))
        items[split] = pool[:n]
        print(f"       unknown/{split}: 从 {len(pool)} 条中抽取 {n} 条")
    return items


def cut_noise_to_clips(noise_path):
    """把一条长噪声切成若干 1 秒片段（帧移 0.5 秒）。

    返回 [(特征, 片段起始秒数), ...]，起始秒数用于记录文件名。
    """
    wav, sr = sf.read(noise_path, dtype="float32", always_2d=False)
    if wav.ndim > 1:
        wav = wav.mean(axis=1)
    if sr != 16000:
        raise ValueError(f"{noise_path} 采样率不是 16 kHz")

    clips = []
    for start in range(0, len(wav) - CLIP_SAMPLES + 1, CLIP_SAMPLES // 2):
        clip = wav[start:start + CLIP_SAMPLES]
        clips.append((wav_to_logmel(clip), start / 16000.0))
    return clips


def collect_silence(root):
    """静音类（标签 11）：从 _background_noise_ 里切 1 秒片段。"""
    noise_dir = root / "_background_noise_"
    noise_files = sorted(noise_dir.glob("*.wav"))
    if len(noise_files) < 6:
        raise RuntimeError("没有找到 6 个背景噪声文件，数据可能不完整")

    # 按固定顺序分配，保证 train/val/test 不重叠
    assign = {
        "train": noise_files[:SILENCE_FILES["train"]],
        "val": noise_files[3:3 + SILENCE_FILES["val"]],
        "test": noise_files[4:4 + SILENCE_FILES["test"]],
    }
    items = {}
    for split, files in assign.items():
        feats = []
        for path in files:
            for feat, start in cut_noise_to_clips(path):
                name = f"_background_noise_/{path.name}@{start:.2f}s"
                feats.append((feat, 11, name))
        items[split] = feats
        print(f"       silence/{split}: {len(feats)} 条（来自 {len(files)} 个噪声文件）")
    return items


def featurize_task(task):
    """多进程 worker：读一条 wav 并提取特征。"""
    path, label = task
    return load_and_featurize(str(path)), label


def main():
    args = parse_args()
    root = Path(args.data_dir).resolve()
    archive = root / ARCHIVE_NAME
    sc_root = root / "speech_commands"
    out_dir = root / "processed"
    out_dir.mkdir(parents=True, exist_ok=True)

    # ---------- 1. 下载 + 解压 ----------
    if not args.skip_download:
        download_with_progress(DATA_URL, archive)
    if not archive.exists():
        raise FileNotFoundError(f"找不到 {archive}，请先下载或去掉 --skip_download")
    extract_archive(archive, sc_root)

    val_list = read_split_list(sc_root / "validation_list.txt")
    test_list = read_split_list(sc_root / "testing_list.txt")

    # ---------- 2. 生成文件清单 ----------
    print("\n[划分数据] 10 个关键词 + unknown + silence")
    keyword_items = collect_keywords(sc_root, val_list, test_list)
    unknown_items = collect_unknown(sc_root, val_list, test_list)
    silence_items = collect_silence(sc_root)

    tasks = {split: [] for split in ["train", "val", "test"]}
    for split in tasks:
        tasks[split] = keyword_items[split] + unknown_items[split]

    # 记录每条特征对应的原始文件名，方便之后分析错误样本
    file_names = {
        split: [path.relative_to(sc_root).as_posix() for path, _ in tasks[split]]
        for split in tasks
    }

    # ---------- 3. 多进程提取特征 ----------
    packed = {}
    total_files = sum(len(v) for v in tasks.values())
    print(f"\n[提取特征] 共 {total_files} 条音频，使用 {args.workers} 个进程")
    with mp.Pool(processes=args.workers) as pool:
        for split in ["train", "val", "test"]:
            feats = []
            desc = f"       {split}"
            for (feat, label), name in zip(
                tqdm(
                    pool.imap(featurize_task, tasks[split], chunksize=32),
                    total=len(tasks[split]), desc=desc,
                ),
                file_names[split],
            ):
                feats.append((feat, label, name))
            # 静音片段是直接算好的，拼到对应集合后面
            feats.extend(silence_items[split])
            packed[split] = feats

    # ---------- 4. 保存 ----------
    print("\n[保存特征]")
    counts = {}
    for split in ["train", "val", "test"]:
        x = np.stack([item[0] for item in packed[split]]).astype(np.float32)
        y = np.array([item[1] for item in packed[split]], dtype=np.int64)
        names = [item[2] for item in packed[split]]
        np.save(out_dir / f"{split}_x.npy", x)
        np.save(out_dir / f"{split}_y.npy", y)
        with open(out_dir / f"{split}_files.txt", "w", encoding="utf-8") as f:
            for name, label in zip(names, y):
                f.write(f"{name}\t{int(label)}\n")
        counts[split] = {CLASSES[i]: int((y == i).sum()) for i in range(len(CLASSES))}
        print(f"       {split}: x={tuple(x.shape)}, y={tuple(y.shape)}")

    # 用训练集统计每个 Mel 频带的均值和标准差（后面做归一化）
    x_train = np.load(out_dir / "train_x.npy")
    mean = x_train.mean(axis=(0, 2)).astype(np.float32)
    std = x_train.std(axis=(0, 2)).astype(np.float32) + 1e-5
    np.savez(out_dir / "stats.npz", mean=mean, std=std)

    meta = {
        "classes": CLASSES,
        "num_train": int(len(np.load(out_dir / "train_y.npy"))),
        "num_val": int(len(np.load(out_dir / "val_y.npy"))),
        "num_test": int(len(np.load(out_dir / "test_y.npy"))),
        "counts": counts,
        "feature": {"n_mels": 40, "n_frames": 98, "sample_rate": 16000},
    }
    with open(out_dir / "meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print("\n[完成] 数据已保存到:", out_dir)
    print(json.dumps({k: meta[k] for k in ["num_train", "num_val", "num_test"]},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
