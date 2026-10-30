# 2026-10-31 两组大作业交付状态

## 三个提交物

| 提交物 | 位置 | 内容 |
| --- | --- | --- |
| 视觉单独包 | `vision/submission/2023302610_肖怀瑾_vision.zip` | 120 文件，13.89 MB；README_FIRST + code/vision + report/（DOCX+PDF）+ docs + manifest + verify_package.py |
| 语音单独目录 | `speech/submission/2023302610_肖怀瑾_kws/` | 18 文件，1.93 MB；code/ + runs/ + report.docx + report.pdf + README.md；自录补齐后再压成同名 zip |
| 两组一起 | `submission/2023302610_肖怀瑾_多媒体大作业.zip` | 139 文件，15.55 MB；vision/ + kws/ + README_FIRST.md |

## 哈希

- 视觉 zip：`9dd92e4d09e8a3edcd9c9ffa5da662d4059a5f6d95f224724e24bc6d63c9bd2e`
- 视觉报告 DOCX：`211d9f9679f434a123add9062fa7b6e81f9566723f0219fc93b3029fabfb8b1b`（82 页，32 图，28 表）
- 视觉报告 PDF：`e9c4ccf3ae82fa78bb90ad634d365aeccd3ff8c2b03e00bf4f5c92366398d7fa`（LibreOffice Kit，87 页；DOCX 的 Word 版 82 页为准）
- 语音 report.pdf：`eceb75851b1b3bf92d8b0ab6320aee8e0ed6d062e70e9b45e6f395319dbe5bc3`（8 页，6 图，6 表）
- 语音 report.docx：`aefcff7c118a560ab0abd1c63bbc7615466c8af083917bac41642a319c33e3cf`
- 合并 zip：`a1d51291466d30b7f312b1acc5a84146537b02314d0aad9c7016551a3098ef1e`

## 验证

- 视觉包自检：118 个文件哈希匹配，报告 DOCX/PDF 可读；解压后 `python -m vision --help` 通过，`pytest vision/tests` 20 项通过。
- 视觉报告 Word 16 统计 82 页，目录页码已更新；封面已去掉实验地点、指导教师两行。
- 语音包报告 DOCX/PDF 均 8 页；`best.pt` 可加载（19,948 参数，epoch 30）；指标与 `metrics.json` 一致。
- 合并包含两个子目录，无 `data/`、权重缓存、`__pycache__` 或 `.pytest_cache`；视觉子包自检通过。

## 待补

自录音频（短词 + 长录音）尚未提供。语音报告第 8 节已如实标注；录音放入 `speech/kws_hw/my_recordings/` 后重跑推理、报告、PDF 和打包。视觉交互记录沿用快照；语音不记录大模型交互。

## 未提交

数据集、预训练权重、特征缓存、视频、Conda 环境、日志和中间预览图。视觉报告已嵌入图表；语音包带 `best.pt`、三张结果图和 `metrics.json`。
