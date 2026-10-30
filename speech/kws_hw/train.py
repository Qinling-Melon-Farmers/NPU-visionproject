"""第 2 步：训练关键词分类模型。

运行:
    python train.py              # 默认训练 40 个 epoch

训练完成后 runs/ 目录下会有:
    best.pt              验证集准确率最高的模型
    history.json         每个 epoch 的 loss / acc
    training_curves.png  训练曲线
"""

import argparse
import json
import os
import random
import time
from pathlib import Path

import matplotlib
matplotlib.use("Agg")          # 服务器上画图不弹窗
import matplotlib.pyplot as plt
import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset
from tqdm import tqdm

from model import DSConvNet, count_parameters


class KWSData(Dataset):
    """从 .npy 读特征，训练时做轻量数据增强。"""

    def __init__(self, data_dir, split, mean, std, augment=False):
        self.x = np.load(Path(data_dir) / f"{split}_x.npy")
        self.y = np.load(Path(data_dir) / f"{split}_y.npy")
        self.mean = mean[:, None].astype(np.float32)   # (40, 1)
        self.std = std[:, None].astype(np.float32)     # (40, 1)
        self.augment = augment

    def __len__(self):
        return len(self.y)

    def __getitem__(self, index):
        x = self.x[index].astype(np.float32)
        x = (x - self.mean) / self.std
        if self.augment:
            x = time_shift(x)
            x = spec_augment(x)
        return torch.from_numpy(x).unsqueeze(0), int(self.y[index])


def time_shift(x, max_shift=8):
    """时间方向随机平移 ±80 ms（8 帧 x 10 ms）。"""
    shift = np.random.randint(-max_shift, max_shift + 1)
    if shift == 0:
        return x
    out = np.zeros_like(x)
    if shift > 0:
        out[:, shift:] = x[:, :-shift]
    else:
        out[:, :shift] = x[:, -shift:]
    return out


def spec_augment(x, max_freq=6, max_time=6):
    """随机遮住几块频率/时间区域（SpecAugment 的简化版）。"""
    x = x.copy()
    n_mels, n_frames = x.shape
    for _ in range(np.random.randint(0, 2)):       # 0 或 1 个频率遮挡
        width = np.random.randint(0, max_freq + 1)
        if width > 0:
            start = np.random.randint(0, n_mels - width + 1)
            x[start:start + width, :] = 0.0
    for _ in range(np.random.randint(0, 2)):       # 0 或 1 个时间遮挡
        width = np.random.randint(0, max_time + 1)
        if width > 0:
            start = np.random.randint(0, n_frames - width + 1)
            x[:, start:start + width] = 0.0
    return x


def set_seed(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def train_one_epoch(model, loader, criterion, optimizer, device):
    model.train()
    total_loss, correct, total = 0.0, 0, 0
    for x, y in tqdm(loader, desc="      train", leave=False):
        x = x.to(device, non_blocking=True)
        y = y.to(device, non_blocking=True)

        optimizer.zero_grad(set_to_none=True)
        logits = model(x)
        loss = criterion(logits, y)
        loss.backward()
        optimizer.step()

        total_loss += loss.item() * y.size(0)
        correct += (logits.argmax(dim=1) == y).sum().item()
        total += y.size(0)
    return total_loss / total, correct / total


@torch.no_grad()
def evaluate(model, loader, criterion, device):
    model.eval()
    total_loss, correct, total = 0.0, 0, 0
    for x, y in tqdm(loader, desc="      val  ", leave=False):
        x = x.to(device, non_blocking=True)
        y = y.to(device, non_blocking=True)
        logits = model(x)
        loss = criterion(logits, y)

        total_loss += loss.item() * y.size(0)
        correct += (logits.argmax(dim=1) == y).sum().item()
        total += y.size(0)
    return total_loss / total, correct / total


def plot_history(history, save_path):
    epochs = range(1, len(history["train_loss"]) + 1)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))

    axes[0].plot(epochs, history["train_loss"], "o-", label="Train")
    axes[0].plot(epochs, history["val_loss"], "s-", label="Val")
    axes[0].set_xlabel("Epoch")
    axes[0].set_ylabel("Loss")
    axes[0].set_title("Loss")
    axes[0].legend()
    axes[0].grid(alpha=0.3)

    axes[1].plot(epochs, [a * 100 for a in history["train_acc"]], "o-", label="Train")
    axes[1].plot(epochs, [a * 100 for a in history["val_acc"]], "s-", label="Val")
    axes[1].set_xlabel("Epoch")
    axes[1].set_ylabel("Accuracy (%)")
    axes[1].set_title("Accuracy")
    axes[1].legend()
    axes[1].grid(alpha=0.3)

    fig.tight_layout()
    fig.savefig(save_path, dpi=150)
    plt.close(fig)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_dir", type=str, default="data/processed")
    parser.add_argument("--save_dir", type=str, default="runs")
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--batch_size", type=int, default=128)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--weight_decay", type=float, default=1e-4)
    parser.add_argument("--width", type=int, default=32, help="模型通道数")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--num_workers", type=int, default=0)
    parser.add_argument("--no_augment", action="store_true",
                        help="关闭数据增强（做对比实验用）")
    parser.add_argument("--cpu", action="store_true", help="强制用 CPU 训练")
    return parser.parse_args()


def main():
    args = parse_args()
    set_seed(args.seed)

    data_dir = Path(args.data_dir)
    save_dir = Path(args.save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)

    with open(data_dir / "meta.json", "r", encoding="utf-8") as f:
        meta = json.load(f)
    classes = meta["classes"]
    stats = np.load(data_dir / "stats.npz")
    mean, std = stats["mean"], stats["std"]

    device = torch.device("cpu" if args.cpu or not torch.cuda.is_available() else "cuda")
    if device.type == "cuda":
        print(f"[设备] GPU: {torch.cuda.get_device_name(0)}")
    else:
        print("[设备] CPU（会比较慢，但也能跑完）")

    train_set = KWSData(data_dir, "train", mean, std, augment=not args.no_augment)
    val_set = KWSData(data_dir, "val", mean, std, augment=False)
    train_loader = DataLoader(
        train_set, batch_size=args.batch_size, shuffle=True,
        num_workers=args.num_workers, pin_memory=(device.type == "cuda"),
    )
    val_loader = DataLoader(
        val_set, batch_size=args.batch_size, shuffle=False,
        num_workers=args.num_workers, pin_memory=(device.type == "cuda"),
    )
    print(f"[数据] train={len(train_set)}  val={len(val_set)}  classes={len(classes)}")

    model = DSConvNet(num_classes=len(classes), width=args.width).to(device)
    print(f"[模型] 参数量 = {count_parameters(model) / 1000:.2f} K")

    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=args.lr, weight_decay=args.weight_decay
    )
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=args.epochs
    )

    history = {"train_loss": [], "train_acc": [], "val_loss": [], "val_acc": [], "lr": []}
    best_acc = 0.0
    start_time = time.time()

    for epoch in range(1, args.epochs + 1):
        print(f"\n[Epoch {epoch:02d}/{args.epochs}]  lr={optimizer.param_groups[0]['lr']:.2e}")
        train_loss, train_acc = train_one_epoch(
            model, train_loader, criterion, optimizer, device
        )
        val_loss, val_acc = evaluate(model, val_loader, criterion, device)
        scheduler.step()

        history["train_loss"].append(train_loss)
        history["train_acc"].append(train_acc)
        history["val_loss"].append(val_loss)
        history["val_acc"].append(val_acc)
        history["lr"].append(optimizer.param_groups[0]["lr"])

        print(f"      train_loss={train_loss:.4f}  train_acc={train_acc * 100:.2f}%  "
              f"val_loss={val_loss:.4f}  val_acc={val_acc * 100:.2f}%")

        if val_acc > best_acc:
            best_acc = val_acc
            torch.save({
                "model": model.state_dict(),
                "classes": classes,
                "mean": mean,
                "std": std,
                "epoch": epoch,
                "val_acc": val_acc,
                "width": args.width,
                "config": vars(args),
            }, save_dir / "best.pt")
            print(f"      [保存] 新的最好模型 val_acc={best_acc * 100:.2f}%")

    elapsed = time.time() - start_time
    with open(save_dir / "history.json", "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    plot_history(history, save_dir / "training_curves.png")

    print("\n" + "=" * 60)
    print(f"训练结束，用时 {elapsed / 60:.1f} 分钟")
    print(f"最好的验证集准确率: {best_acc * 100:.2f}%")
    print(f"模型保存位置: {save_dir / 'best.pt'}")
    print("下一步: python evaluate.py")
    print("=" * 60)


if __name__ == "__main__":
    main()
