# 2026-10-28 交付状态

三个指定模型、约定对照、真实运行与严格 FP32 独立重放已通过；20 项测试通过，`verify` 返回 `passed`。报告已按学校模板重排并重写正文，附录 C/D 改为可检索的分阶段记录。

| 产物 | 路径与状态 |
| --- | --- |
| Word 报告 | `delivery-20261028/vision_report.docx`；SHA256 `211d9f9679f434a123add9062fa7b6e81f9566723f0219fc93b3029fabfb8b1b`；Word 16 更新目录；正文 30 页，全篇 82 页；32 图、28 表；封面已去掉实验地点和指导教师两行 |
| PDF 报告 | `delivery-20261028/vision_report.pdf`；SHA256 `e9c4ccf3ae82fa78bb90ad634d365aeccd3ff8c2b03e00bf4f5c92366398d7fa`；LibreOffice Kit 转换，字体替换后 87 页；DOCX 的 Word 版 82 页为准 |
| 报告生成器 | `build_report_v2.py`；配套 `docx_helpers.py`、`report_sections.py`、`report_appendices.py`、`add_references.py`；一级标题楷体、二级标题黑体、正文宋体 |
| 图表 | `figures_v2/`；中文标注的方法对比、视频对比、摘要分数和两张帧间相似度图；其余沿用真实运行图 |
| 学生交互 | 附录 C；快照内 9 条自由文本提示、2 批 5 个结构化问题、33 条编程大模型可见回复、46 条记录 |
| 代理协作 | 附录 D；79 条独立归档事件，17 条可读、62 条加密，不计学生轮数 |
| 交互核验 | `../logs/interactions_20261023_audit02.jsonl` 与 `.audit.json`；源文件行号、SHA256 保留；2026-10-28 审阅未写入附录 |
| 严格完整性限制 | 62 条代理间正文仍加密不可读；未解密、未编造补齐；报告只在附录 D 保留缺口说明 |
| 代码和报告包 | `../submission/2023302610_肖怀瑾_vision.zip`；120 文件；13.89 MB；SHA256 `9dd92e4d09e8a3edcd9c9ffa5da662d4059a5f6d95f224724e24bc6d63c9bd2e`；顶层为 README_FIRST、code/、report/（DOCX+PDF）、docs/、manifest/、verify_package.py |
| 本地摘要 | 配置资源目录下 `cache/summary/visual-20261023-fp32/`；三预算离屏播放与逐帧对齐记录通过 |
| 验证记录 | `../outputs/visual-20261023-fp32/verification_20261028T205819476067.json`；三份 replay；20 项测试；旧 v3 验证已归档到 `archive/submission_verification_20261028_v3.json` |
| Git | 已关联 origin 并按阶段本地提交；截至本次交付未执行 push，未重写远端历史 |

正式数值：图像 GeM 主图库 P@5=0.9880、mAP=0.727820；视频主方法与去 CNN 对照均 20/20 命中、mAP=1.0000；摘要 15% 预算实际 1,585/10,597 帧、平均 F1=0.680512，随机基线 0.195264±0.076892。报告如实呈现图像最大池化略高、视频任务未拉开差异及摘要单视频局限。

姓名、学号、班级、学院和专业已按同机课程报告填写；实验地点和指导教师两行已从封面删除。报告正文把代码生成与运行、核验分开说明，附录 C/D 保留原始可见记录。

原始任务书和课件 SHA256 与初始读取一致；原 `pytorch` 环境未修改。旧报告 `delivery-final-20261023/vision_report.docx`、旧提交包、失败日志和早期草稿均保留，没有删除已有文件。Word 的 PDF 导出曾卡顿，本次以 DOCX 和 LibreOffice 页面渲染检查为准；PDF 不是交付必需项。
