# 结果与证据索引

正式结果目录：`outputs/visual-20261023-fp32`（不随包提交）。报告中的数字来自该目录的 `results.json`、`verification_*.json`、`replay_*.json` 和 `summary/playback_review.json`。

| 实验 | 关键结果 | 报告位置 |
| --- | --- | --- |
| 图像检索 GeM | 400 次查询、6,800 张图库；P@5 = 0.9880，mAP = 0.727820；最大池化对照 mAP = 0.7306 | 第 3 章、图 1-5、表 4-6 |
| 视频检索 ViSiL | 20 个查询、90 个候选；Top-3 命中 20/20，mAP = 1.0000；去 CNN 对照同为 20/20 | 第 4 章、图 6-10、表 7-10 |
| 视频摘要 DSNet AF | TVSum `AwmHb44_ouw`：10,597 帧；选中 1,585 帧，比例 14.9571%；平均 F1 = 0.680512；随机基线 0.195264 ± 0.076892 | 第 5 章、图 11-14、表 11-16 |

## 验证

- 三个实验 `results.json` 的 `status` 均为 `completed`。
- 三份独立重放 `replay_image.json`、`replay_video.json`、`replay_summary.json` 均为 `passed`。
- 摘要导出帧数与选帧一致，实际播放检查 `summary/playback_review.json` 为 `passed`。
- `python -m vision verify --run-id visual-20261023-fp32` 通过。
- `pytest vision/tests`：20 项通过。

## 报告

`report/vision_report.docx`：82 页（Word 16），正文 30 页，32 图，28 表，目录 48 项。`report/vision_report.pdf` 为 PDF 阅读版，由 LibreOffice Kit 转换，字体替换后为 87 页；以 DOCX 的 Word 页数为准。封面、摘要、目录、正文、参考文献和附录 A-D 均已生成；附录 C 是学生与编程大模型的可见交互，附录 D 是代理协作记录，含 62 条加密正文的缺口说明。

## 文件对应

- 代码入口：`code/vision/__main__.py`
- 三实验实现：`code/vision/experiments/{image,video,summary}.py`
- 资源与核验：`code/vision/common/resources.py`、`common/verify.py`
- 配置：`code/vision/configs/default.yaml`
- 作者代码：`code/vision/vendor/`
- 报告生成：`code/vision/reports/build_report_v2.py` 及同目录模块

## 边界

包内没有数据、权重、特征或视频，不能只靠本包重跑出同样的指标；需要按 `docs/REPRODUCE.md` 准备资源。报告中的图表已经嵌入，阅读报告不需要这些资源。
