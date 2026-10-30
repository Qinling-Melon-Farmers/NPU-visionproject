# 关键词唤醒大作业 · 代码

详细步骤请看《指导文档.pdf》，这里只放最简流程。

## 0. 安装依赖

先按文档第 3 章安装好 PyTorch（GPU 版），然后：

```bash
pip install -r requirements.txt
```

## 1. 准备数据

```bash
python prepare_data.py
```

下载约 1.5 GB，解压后约 2 GB，处理完约 4 GB。第一次运行需要几分钟。

## 2. 训练

```bash
python train.py
```

默认 40 个 epoch，单卡 GPU 通常几分钟到十几分钟。
模型只有约 2 万个参数。

## 3. 评估

```bash
python evaluate.py
```

结果在 `runs/`：
- `confusion_matrix.png`
- `det_curve.png`
- `classification_report.txt`
- `metrics.json`

## 4. 识别自己的录音

```bash
python infer.py 你的录音.wav
```

## 5. 加分项：长音频检测

压缩包里自带一个 7 秒的 `demo_long.wav`，可以直接试：

```bash
python detect.py demo_long.wav --target yes --threshold 0.9
```

也可以换成你自己的长录音：

```bash
python detect.py 你的长录音.wav --target yes --threshold 0.9
```

## 文件说明

| 文件 | 作用 |
| --- | --- |
| `features.py` | 读取 wav + 提取 40×98 log-Mel 特征 |
| `prepare_data.py` | 下载数据、划分 12 类、提取并保存特征 |
| `model.py` | 小型 DS-CNN 模型（约 19.95 K 参数） |
| `train.py` | 训练脚本 |
| `evaluate.py` | 测试集评估 + 混淆矩阵 + DET 曲线 |
| `infer.py` | 单条 wav 推理 |
| `detect.py` | 长音频滑动窗口唤醒词检测 |
| `requirements.txt` | 除 torch 以外的依赖 |
| `demo_long.wav` | 7 秒示例音频：yes → stop → yes |
