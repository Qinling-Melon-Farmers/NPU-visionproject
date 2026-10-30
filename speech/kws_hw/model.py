"""一个很小的 DS-CNN（Depthwise Separable CNN）关键词分类模型。

输入:  (batch, 1, 40, 98) 的 log-Mel 特征
输出:  (batch, num_classes) 的类别分数（logits）

整个模型只有约 2 万个参数，笔记本 GPU 甚至 CPU 都能训练。
"""

import torch.nn as nn
import torch.nn.functional as F


class DSBlock(nn.Module):
    """深度可分离卷积块：3x3 depthwise + 1x1 pointwise。"""

    def __init__(self, in_ch, out_ch):
        super().__init__()
        # 每个通道单独做 3x3 卷积，参数量只有普通卷积的 1/out_ch
        self.depthwise = nn.Conv2d(
            in_ch, in_ch, kernel_size=3, padding=1, groups=in_ch, bias=False
        )
        self.bn1 = nn.BatchNorm2d(in_ch)
        # 1x1 卷积负责融合通道
        self.pointwise = nn.Conv2d(in_ch, out_ch, kernel_size=1, bias=False)
        self.bn2 = nn.BatchNorm2d(out_ch)

    def forward(self, x):
        x = F.relu(self.bn1(self.depthwise(x)))
        x = F.relu(self.bn2(self.pointwise(x)))
        return x


class DSConvNet(nn.Module):
    def __init__(self, num_classes=12, width=32):
        super().__init__()
        # 第 0 层：普通 3x3 卷积，把 1 通道特征图变成 width 通道
        self.stem = nn.Sequential(
            nn.Conv2d(1, width, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(width),
            nn.ReLU(inplace=True),
        )
        # 4 个 DS 块，每块后面接 2x2 最大池化（时间、频率各减半）
        self.blocks = nn.Sequential(
            DSBlock(width, width),        # 40 x 98 -> 20 x 49
            nn.MaxPool2d(2),
            DSBlock(width, width * 2),    # 20 x 49 -> 10 x 24
            nn.MaxPool2d(2),
            DSBlock(width * 2, width * 2),  # 10 x 24 -> 5 x 12
            nn.MaxPool2d(2),
            DSBlock(width * 2, width * 4),  # 5 x 12 -> 2 x 6
            nn.MaxPool2d(2),
        )
        # 全局平均池化 + 全连接分类
        self.head = nn.Sequential(
            nn.AdaptiveAvgPool2d(1),
            nn.Flatten(),
            nn.Dropout(0.1),
            nn.Linear(width * 4, num_classes),
        )

    def forward(self, x):
        x = self.stem(x)
        x = self.blocks(x)
        return self.head(x)


def count_parameters(model):
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


if __name__ == "__main__":
    import torch

    net = DSConvNet(num_classes=12, width=32)
    x = torch.randn(2, 1, 40, 98)
    print("输入:", tuple(x.shape), "输出:", tuple(net(x).shape))
    print("参数量: %.2f K" % (count_parameters(net) / 1000))
