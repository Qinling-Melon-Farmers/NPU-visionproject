# 关键词唤醒大作业提交说明

学号 2023302610　姓名 肖怀瑾　2026-10-31

## 目录

```text
code/        教师教学代码的 8 个 Python 文件、README、requirements.txt、demo_long.wav
runs/        best.pt、训练曲线、混淆矩阵、DET 曲线、分数分布、分类报告、训练历史、metrics.json
report.docx  8 页实验报告 Word 版
report.pdf   8 页实验报告 PDF 版
```

本包只放提交所需文件；数据、特征缓存、Conda 环境、训练日志和中间图表不在包内。

## 运行

```powershell
conda run -p D:\Anaconda3\envs\pytorch python -s code\train.py
conda run -p D:\Anaconda3\envs\pytorch python -s code\evaluate.py
conda run -p D:\Anaconda3\envs\pytorch python -s code\detect.py code\demo_long.wav --target yes --threshold 0.9
```

数据路径按 `--data_dir` 传入，默认 `data`。环境为 Python 3.12.8 / PyTorch 2.5.1+cu118；依赖见 `requirements.txt`。

## 结果

测试集 3307 条，12 类准确率 94.62%，宏 F1 0.9489；以 yes 为唤醒词时 ROC-AUC 0.9992，EER 1.47%。四组消融和长音频阈值实验见报告第 7、8 节。报告数字由脚本从 `metrics.json` 等结果文件写入。

## 自录音频

第 8 步与长音频加分项（8.2 节）已用本人 15 条录音（10 个关键词、2 个词表外词、
2 条中文词、1 条 11.4 秒长录音）完成，结果在报告第 8 节：9/10 关键词识别正确，
非关键词均归入 unknown，长录音在三个阈值下均准确检出 2 次 yes。录音文件与转码
脚本不在提交包内。
