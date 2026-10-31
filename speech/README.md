# 语音大作业（关键词唤醒 KWS）复现说明

本目录是《多媒体技术》语音部分大作业：在 Google Speech Commands v0.01 上从零训练
12 类关键词唤醒模型（DS-CNN，约 19.95K 参数），完成训练、评估、消融实验与长音频
唤醒检测（加分项）。代码基于教师提供的教学代码 `kws_code.zip`（保留原 README 与
署名，算法部分未改动）；本仓库新增的脚本位于 `speech/scripts/` 与 `speech/reports/`。

## 环境与配置

- Conda 环境：`D:\Anaconda3\envs\pytorch`（用户指定的既有环境）。
- 已核验版本（见 `logs/environment-check-20261031.txt`）：
  Python 3.12.8 / PyTorch 2.5.1+cu118 / CUDA RTX 4060 Laptop GPU / numpy 2.2.6 /
  scipy 1.15.3 / scikit-learn 1.6.1 / matplotlib 3.10.0 / tqdm 4.67.1。
- 本次在环境内补装 `soundfile 0.14.0` 与 `python-docx 1.2.0`
  （`conda run -p D:\Anaconda3\envs\pytorch python -m pip install soundfile python-docx`），
  未升级/改动 torch、numpy 等任何核心包。
- 统一运行方式（`-s` 隔离用户级包）：

```powershell
conda run -p D:\Anaconda3\envs\pytorch python -s <脚本> <参数>
```

## 公开数据与准备

- 数据集：Speech Commands v0.01，官方 URL
  `http://download.tensorflow.org/data/speech_commands_v0.01.tar.gz`（约 1.5 GB，
  MD5 `3cd23799cb2bbdec517f1cc028f8d43c`，CC BY 4.0，仅用于课程学习）。
- 校园网单连接限速，使用 `scripts/download_dataset_parallel.sh` 对官方 URL 做
  32 段 Range 并行下载（支持断点续跑；必要时对当前进程临时注入
  `http_proxy/https_proxy`，不改全局配置），完成后 `md5sum` 校验。
- 数据放 `E:\MultimediaCourseAssets\speech\data`（脚本原生支持 `--data_dir`，
  无需 junction）。

```powershell
bash speech/scripts/download_dataset_parallel.sh
conda run -p D:\Anaconda3\envs\pytorch python -s speech/kws_hw/prepare_data.py --data_dir E:/MultimediaCourseAssets/speech/data
conda run -p D:\Anaconda3\envs\pytorch python -s speech/scripts/verify_data.py
```

核验点：train/val/test = 21470 / 3096 / 3307，形状 (N, 40, 98)，12 类，
`stats.npz` 仅由训练集统计。结果写入 `outputs/data_summary.json`。

## 训练、评估与消融（均在 speech/kws_hw 下运行）

```powershell
cd speech\kws_hw
conda run -p D:\Anaconda3\envs\pytorch python -s train.py --data_dir E:/MultimediaCourseAssets/speech/data/processed
conda run -p D:\Anaconda3\envs\pytorch python -s evaluate.py --data_dir E:/MultimediaCourseAssets/speech/data/processed
# 消融三组（同测试集同评估脚本）
conda run -p D:\Anaconda3\envs\pytorch python -s train.py --data_dir E:/MultimediaCourseAssets/speech/data/processed --epochs 20 --save_dir runs_20
conda run -p D:\Anaconda3\envs\pytorch python -s train.py --data_dir E:/MultimediaCourseAssets/speech/data/processed --no_augment --save_dir runs_noaug
conda run -p D:\Anaconda3\envs\pytorch python -s train.py --data_dir E:/MultimediaCourseAssets/speech/data/processed --width 48 --save_dir runs_w48
# 每组分别 evaluate（--checkpoint / --save_dir 换成对应目录）
```

运行日志保存在 `speech/logs/`；各 run 的小型证据（metrics.json、图表、错误列表）
拷贝到 `speech/outputs/` 入库，`best.pt` 与 data/ 不入 Git。

## 推理套件、错误分析与报告

```powershell
conda run -p D:\Anaconda3\envs\pytorch python -s speech/scripts/run_inference_suite.py   # 示例推理+长音频阈值实验+自录入口
conda run -p D:\Anaconda3\envs\pytorch python -s speech/scripts/make_error_analysis.py   # 错误样本谱图对照
conda run -p D:\Anaconda3\envs\pytorch python -s speech/scripts/summarize_ablation.py    # 消融汇总
conda run -p D:\Anaconda3\envs\pytorch python -s speech/reports/build_report.py          # 生成 docx
```

报告 docx 由 Word 16 COM（`ExportAsFixedFormat`）导出 PDF——本机未安装
LibreOffice，8 页语音报告导出正常（vision 82 页长报告曾有 COM 卡顿记录，故当时改用
其它渲染方式；本机若装 LibreOffice 也可 `soffice --headless --convert-to pdf`）。
提交材料采用两份形态：`submission/2023302610_肖怀瑾_kws/` 可读目录
（code/ + runs/ + report.docx + report.pdf + README.md）与同名 zip；
合并包见根目录 `submission/`。均不含 data/ 与环境。

## 自录音频入口

原始录音（任意格式，m4a/mp3 均可）放入 `speech/kws_hw/my_recordings_raw/`，
运行 `scripts/convert_recordings.py` 批量转成 16 kHz 单声道 wav 到
`speech/kws_hw/my_recordings/`（文件名按《自录音频准备清单.md》映射）；已是 wav
的直接放入后者。然后重跑 `run_inference_suite.py`——脚本自动区分短音频（单条识别）
与长音频（0.5/0.9/0.99 三阈值滑窗检测），更新 `outputs/baseline/inference_results.json`
与对应图；再跑 `build_report.py` 与 Word 导出同步报告（或直接运行
`scripts/refresh_deliverables.ps1` 一键完成）。2026-10-31 的 15 条自录录音已按此流程
处理并写入报告第 8 节。
