# 语音大作业交付记录（2026-10-31）

## 交付物

| 文件 | 说明 |
| --- | --- |
| `kws_report.docx` | 实验报告 Word 版（正文 8 页，6 图 7 表，作者属性=肖怀瑾） |
| `kws_report.pdf` | 实验报告 PDF（8 页，Word 16 COM 导出，ComputeStatistics 校验） |
| `../../submission/2023302610_肖怀瑾_kws.zip` | 课程提交包：code/ + runs/（best.pt + 图表 + metrics.json 等）+ report.pdf，共 20 文件，1.11 MB |

- 提交包 SHA256：`ee4497adcba0985036136c1a5cf25649772e2e32f376497ca3e75745c29623ec`
- 报告数字全部由 `build_report.py` 程序化读取 `outputs/` 下 evidence JSON 写入，未手抄。

## PDF 转换方式说明

本机未安装 LibreOffice；按 documents 技能要求先尝试安装：TUNA 镜像 MSI 按用户安装
失败（错误 1603，需管理员权限），winget 不存在，故按技能规则回退到本机 Word 16 COM
（`ExportAsFixedFormat`）导出 PDF，导出前确认无用户 Word 实例在运行，导出正常未卡住。

## 待办（用户侧）

- 自录音频（指导文档第 7 步与 8.2 节加分项）：将 16 kHz 单声道 wav 放入
  `speech/kws_hw/my_recordings/`，重跑 `speech/scripts/run_inference_suite.py` 与
  `speech/reports/build_report.py` 后重导出 PDF、重打包即可更新报告；当前报告第 8 节
  已如实标注"自录音频尚未提供"。
