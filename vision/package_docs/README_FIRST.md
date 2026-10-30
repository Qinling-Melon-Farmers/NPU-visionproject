# 多媒体技术视觉实验提交包

肖怀瑾　2023302610　2026-10-31

这个包对应《学生实验任务书》和《多媒体实验介绍》的视觉部分：GeM 图像检索、ViSiL 视频检索、DSNet 无锚框视频摘要，以及涵盖三个实验的 Word 报告。

## 先看什么

1. `report/vision_report.docx`：82 页 Word 最终报告；`report/vision_report.pdf` 是便于直接阅读的 PDF 版。
2. `docs/REQUIREMENTS_COVERAGE.md`：任务书与课件要求到报告章节、代码和证据的对应表。
3. `code/vision/README.md`：代码级复现说明。
4. `docs/REPRODUCE.md`：环境、数据、命令和预期输出。

## 目录

```text
code/vision/        课程代码、作者代码、配置、清单、测试和运行脚本
report/             Word 与 PDF 最终报告
docs/               复现说明、证据索引、许可证、交互审计、要求覆盖表
manifest/           文件清单和 SHA256
verify_package.py   解压后的哈希与结构自检
```

## 最短检查

```powershell
cd code
python -m vision --help
python -m pytest vision/tests -q
```

本包不含数据集、模型权重、特征缓存、视频、日志或个人 Conda 环境。图像检索、视频检索和摘要实验使用的公开资源、权重和 SHA256 记录在 `code/vision/manifests/`；按 `docs/REPRODUCE.md` 重新准备后可以复跑。

## 已知边界

- 视觉报告的交互附录来自已保存的用户可见记录；62 条代理间加密正文无法读取，附录 D 只保留元数据和缺口，不重建原文。
- 数据与权重体积大，不随包提交；报告中的指标、图和表均来自本地真实运行，结果目录和重放记录见正文附录。
- 本包是视觉部分单独提交版；与语音部分合并的版本另见 `2023302610_肖怀瑾_多媒体大作业.zip`。
