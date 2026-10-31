# 语音大作业交付记录（2026-10-31，自录版 v2）

## 交付物

| 文件 | 说明 |
| --- | --- |
| `kws_report.docx` | 实验报告 Word 版（8 页，6 图 6 表，作者属性=肖怀瑾，一级标题楷体/二级黑体/正文宋体；第 8 节含 15 条自录结果） |
| `kws_report.pdf` | 实验报告 PDF（8 页，Word 16 COM 导出；SHA256 `84ed5f5baa339a4ce2495d53878e6d7204f33ead053f7202d4b7b546de461973`） |
| `../../submission/2023302610_肖怀瑾_kws/` | 可读提交目录：code/ + runs/ + report.docx + report.pdf + README.md，18 文件；已同步自录版报告 |
| `../../submission/2023302610_肖怀瑾_kws.zip` | 提交 zip（目录平铺打包，1.80 MB；SHA256 `b0c031e4b48624767dc94f44b68bdb19e43533ea53fcc7ed1c62c315c0d5afd0`） |

报告 DOCX SHA256：`d33628515014caab3c8c9ec1662b10cec76acda139862f81ae2ef02c6ed7c7fa`。
报告数字全部由 `build_report.py` 程序化读取 `outputs/` 下 evidence JSON 写入，未手抄。窗函数按教师代码实际实现写为 Hann，并在正文注明指导文档文字为 Hamming。

## 自录音频（2026-10-31 完成）

15 条本人录音（zip 提供 m4a，经 `scripts/convert_recordings.py` 借 multimedia-vision
环境 ffmpeg 转 16 kHz 单声道 wav，命名按《自录音频准备清单.md》映射）：
10 个英文关键词 9 个 top-1 正确（up→off 为与测试集混淆矩阵方向一致的真实混淆，
语音完整落在 1 秒窗口内）；hello、house 与中文"是""停"共 4 条非关键词全部归入
unknown 类；长录音 11.4 秒在 0.5/0.9/0.99 三阈值下均准确检出 2 次 yes
（t=2.75 s、7.25 s）、无误触发。原始 m4a 保留在 `kws_hw/my_recordings_raw/`（不入库）。

## PDF 转换说明

本机没有独立 LibreOffice。此前记录"Word 16 COM 导出会卡住"来自 vision 82 页长报告；
本 8 页语音报告用 Word 16 COM（`ExportAsFixedFormat`）实测三次均正常导出（约数秒），
当前 PDF 即 COM 导出。若环境有 LibreOffice，也可 `soffice --headless --convert-to pdf` 替代。

## 提交目录

```text
2023302610_肖怀瑾_kws/
├─ README.md
├─ code/          8 个 Python 文件 + README + requirements.txt + demo_long.wav
├─ runs/          best.pt + confusion_matrix.png + det_curve.png + training_curves.png + metrics.json
├─ report.docx    8 页 Word 版（含自录结果）
└─ report.pdf     8 页 PDF 版（含自录结果）
```

不含 data/、特征缓存、日志、Conda 环境、my_recordings/ 与 my_recordings_raw/。
四组消融、demo 与自录长音频对比在报告正文，不额外复制中间图。

## 遗留说明

- 错误分析基于波形/log-Mel 谱图检查（报告已如实注明未做人耳试听），如需完全对齐
  指导文档 10.2 节的"听一遍"，需本人抽听 4 条 misclassified 样本并补 1~2 句听感。
- 根目录 `AUDIT_PLAN_20261031.md` 为本轮核验计划；P0-1、P1-3、P1-4、P1-8 已在
  42da2ea 修复，P1-5（自录长音频三阈值）与 P1-7（转码脚本）在本次补齐，
  P1-1 文档一致性已同步（README/EXPERIMENT_PLAN/AGENTS.md）。
