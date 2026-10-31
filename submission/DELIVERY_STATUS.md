# 2026-10-31 两组大作业交付状态（自录完成版 v2）

## 三个提交物

| 提交物 | 位置 | 内容 |
| --- | --- | --- |
| 视觉单独包 | `vision/submission/2023302610_肖怀瑾_vision.zip` | 120 文件，13.89 MB；README_FIRST + code/vision + report/（DOCX+PDF）+ docs + manifest + verify_package.py |
| 语音提交目录 + zip | `speech/submission/2023302610_肖怀瑾_kws/` 与同名 `.zip` | 目录 18 文件（code/ + runs/ + report.docx + report.pdf + README.md）；zip 平铺 19 条目，1.80 MB |
| 两组一起 | `submission/2023302610_肖怀瑾_多媒体大作业.zip` | 139 文件，15.69 MB；vision/ + kws/ + README_FIRST.md |

## 哈希

- 视觉 zip：`9dd92e4d09e8a3edcd9c9ffa5da662d4059a5f6d95f224724e24bc6d63c9bd2e`
- 视觉报告 DOCX：`211d9f9679f434a123add9062fa7b6e81f9566723f0219fc93b3029fabfb8b1b`（82 页，32 图，28 表）
- 视觉报告 PDF：`e9c4ccf3ae82fa78bb90ad634d365aeccd3ff8c2b03e00bf4f5c92366398d7fa`（LibreOffice Kit，87 页；DOCX 的 Word 版 82 页为准）
- 语音 report.pdf：`84ed5f5baa339a4ce2495d53878e6d7204f33ead053f7202d4b7b546de461973`（8 页，6 图 6 表，Word 16 COM 导出，含自录结果）
- 语音 report.docx：`d33628515014caab3c8c9ec1662b10cec76acda139862f81ae2ef02c6ed7c7fa`
- 语音 zip：`b0c031e4b48624767dc94f44b68bdb19e43533ea53fcc7ed1c62c315c0d5afd0`
- 合并 zip：`95aa85c2e71c09b44d00826bcc85b32b798117126365eff379cfe2a801e898ce`

## 验证

- 视觉包自检：118 个文件哈希匹配，报告 DOCX/PDF 可读；解压后 `python -m vision --help` 通过，`pytest vision/tests` 20 项通过。
- 视觉报告 Word 16 统计 82 页，目录页码已更新；封面已去掉实验地点、指导教师两行。
- 语音包报告 DOCX/PDF 均 8 页；`best.pt` 可加载（19,948 参数，epoch 30）；指标与 `metrics.json` 一致。
- 自录验证：15 条录音（10 关键词 9 对、4 非关键词全归 unknown、长录音 2 次 yes/三阈值一致）已写入报告第 8 节并同步进目录与两份 zip。
- 合并包含两个子目录，无 `data/`、权重缓存、`__pycache__` 或 `.pytest_cache`；视觉子包自检通过。

## 遗留

错误分析未做人耳试听（报告如实注明，基于波形/谱图声学检查）；如需完全对齐指导文档
10.2 节可由本人抽听 4 条 misclassified 样本后补 1~2 句听感再重导出。视觉交互记录沿用
快照；语音不记录大模型交互。

## 未提交

数据集、预训练权重、特征缓存、视频、Conda 环境、日志、中间预览图与两份 zip 本体
（zip 生成方式与哈希见上，可随时复现）。视觉报告已嵌入图表；语音包带 `best.pt`、
三张结果图和 `metrics.json`。
