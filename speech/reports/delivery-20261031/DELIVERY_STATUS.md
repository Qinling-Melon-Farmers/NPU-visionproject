# 语音大作业交付记录（2026-10-31）

## 交付物

| 文件 | 说明 |
| --- | --- |
| `kws_report.docx` | 实验报告 Word 版（8 页，6 图 6 表，作者属性=肖怀瑾，一级标题楷体/二级黑体/正文宋体） |
| `kws_report.pdf` | 实验报告 PDF（8 页，LibreOffice Kit 转换；SHA256 `eceb75851b1b3bf92d8b0ab6320aee8e0ed6d062e70e9b45e6f395319dbe5bc3`） |
| `../submission/2023302610_肖怀瑾_kws/` | 当前提交目录：code/ + runs/ + report.docx + report.pdf + README.md，18 文件，1.93 MB；自录补齐后再压成同名 zip |

报告 DOCX SHA256：`aefcff7c118a560ab0abd1c63bbc7615466c8af083917bac41642a319c33e3cf`。
报告数字全部由 `build_report.py` 程序化读取 `outputs/` 下 evidence JSON 写入，未手抄。窗函数按教师代码实际实现写为 Hann，并在正文注明指导文档文字为 Hamming。

## PDF 转换说明

本机没有独立 LibreOffice，Word 16 COM 在本机导出该文件会卡住；实际用自带 LibreOffice Kit 将 DOCX 转为 PDF，页数 8。若环境有 LibreOffice，也可用 `soffice --headless --convert-to pdf` 替代。

## 提交目录

```text
2023302610_肖怀瑾_kws/
├─ README.md
├─ code/          8 个 Python 文件 + README + requirements.txt + demo_long.wav
├─ runs/          best.pt + confusion_matrix.png + det_curve.png + training_curves.png + metrics.json
├─ report.docx    8 页 Word 版
└─ report.pdf     8 页 PDF 版
```

不含 data/、特征缓存、日志、Conda 环境或空的 my_recordings/。四组消融和长音频对比在报告正文，不额外复制中间图。

## 待办（用户侧）

- 自录音频（指导文档第 7 步与 8.2 节加分项）：将 16 kHz 单声道 wav 放入
  `speech/kws_hw/my_recordings/`，重跑 `speech/scripts/run_inference_suite.py`、
  `speech/reports/build_report.py`、PDF 转换和打包；当前报告第 8 节已如实标注
  “自录音频尚未提供”。录音补齐后再生成 `2023302610_肖怀瑾_kws.zip`。
