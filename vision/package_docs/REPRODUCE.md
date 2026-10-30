# 视觉实验复现

## 环境

专用 Conda 环境：`E:\MultimediaCourseAssets\envs\multimedia-vision`。Python 3.11.17、PyTorch 2.5.1、CUDA 11.8；版本锁定见 `code/vision/environment-lock-win-64.yml` 与 `environment.yml`。

从 `code/` 目录运行：

```powershell
conda run -p E:\MultimediaCourseAssets\envs\multimedia-vision python -s -c "import sys; print(sys.executable)"
conda run -p E:\MultimediaCourseAssets\envs\multimedia-vision python -s vision/scripts/environment_check.py
```

换存储盘时复制 `vision/configs/default.yaml`，修改 `asset_root` 和 `environment_prefix`，后续命令加 `--config`。

## 资源

数据、权重和视频缓存放在 `asset_root`，不随包提交。公开资源的 URL、SHA256 和划分记录在：

- `code/vision/manifests/image_sources.json`
- `code/vision/manifests/video_sources.json`
- `code/vision/manifests/video_resources.json`
- `code/vision/manifests/summary_sources.json`
- `code/vision/manifests/tvsum_h5_mapping.json`

空资源目录按顺序重建：

```powershell
conda run --no-capture-output -p E:\MultimediaCourseAssets\envs\multimedia-vision python -s -m vision prepare --download --config vision/configs/default.yaml --run-id prepare-01
```

## 三个实验

```powershell
conda run --no-capture-output -p E:\MultimediaCourseAssets\envs\multimedia-vision python -s -m vision image --config vision/configs/default.yaml --run-id visual-repro
conda run --no-capture-output -p E:\MultimediaCourseAssets\envs\multimedia-vision python -s -m vision video --config vision/configs/default.yaml --run-id visual-repro
conda run --no-capture-output -p E:\MultimediaCourseAssets\envs\multimedia-vision python -s -m vision summary --config vision/configs/default.yaml --run-id visual-repro
conda run -p E:\MultimediaCourseAssets\envs\multimedia-vision python -s -m vision verify --run-id visual-repro
```

正式报告使用 `outputs/visual-20261023-fp32`。该目录不在包内，报告中的数字、图表和验收结论均来自该目录；没有数据时不能重新生成同样的图，只能按上面的资源清单重新准备后复跑。

## 报告

`report/vision_report.docx` 已生成并更新目录域。重新生成需要先有正式输出目录，然后运行：

```powershell
conda run -p E:\MultimediaCourseAssets\envs\multimedia-vision python -s vision/reports/build_report_v2.py
```

首次生成后需在 Word 中更新目录和页码域。`vision/reports/make_figures_v2.py` 从结果目录生成中文图；图不随包提交，报告已嵌入最终图。

## 测试

```powershell
conda run -p E:\MultimediaCourseAssets\envs\multimedia-vision python -s -m pytest vision/tests -q
```

测试不需要完整数据；涉及资源路径的测试会按清单检查文件是否存在，缺少资源时跳过或报告缺失。
