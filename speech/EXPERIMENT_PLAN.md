# 语音大作业（关键词唤醒 KWS）实施计划

批准日期：2026-10-31。状态：进入实施；本文件记录完整协议、阶段状态与必要修订。
依据：《音频大作业指导文档.pdf》（42 页）+ `kws_code.zip`（教师教学代码）+ AGENTS.md 通用约定与 2026-10-31 语音部分批准决定。

## 1. 目标与约束

- 在 Google Speech Commands v0.01 上从零训练 12 类关键词唤醒模型（DS-CNN，约 19.95K 参数，log-Mel 40×98 输入）；完成数据准备 → 训练 → 评估 → 推理 → 错误分析；消融至少一组（计划四组）；加分项为长音频唤醒检测与阈值实验。
- 交付：可运行代码 + `runs/best.pt` + 4~8 页 PDF 报告 + 结果图（训练曲线、混淆矩阵、DET 曲线、结果表、消融表）+ 提交包 `2023302610_肖怀瑾_kws.zip`。
- 用户决定（2026-10-31）：语音使用原 `pytorch` 环境（`D:\Anaconda3\envs\pytorch`）；自录音频先跑通留入口；只本地 commit 不 push（复用 origin 仓库）；语音不要求大模型交互记录。

## 2. 目录、环境与运行方式

```text
speech/
├─ EXPERIMENT_PLAN.md          本计划
├─ README.md                   运行说明与依赖信息（收尾阶段写）
├─ kws_hw/                     教师代码解压（保留原 README 署名），我的修改直接在此
│  └─ my_recordings/           自录音频入口（用户 16 kHz 单声道 wav 放这里）
├─ scripts/                    environment_check.py、rerun_infer_detect.py、package_submission.py
├─ logs/                       环境检查输出、各阶段命令与关键输出
├─ outputs/                    各 run 的小型证据文件（metrics.json、图表副本、消融汇总）
├─ reports/                    报告生成脚本与最终 docx/pdf
└─ submission/                 最终提交 zip（不入库）
```

- 环境：`conda run -p D:\Anaconda3\envs\pytorch python -s ...`；禁导 cv2；不升级 torch/numpy；补装依赖仅 `python -m pip install <包>` 并记录版本。兼容问题先环境内最小化解决，回退需用户确认。
- 数据放 `E:\MultimediaCourseAssets\speech\data`：若 prepare_data.py 支持数据目录参数则直接指定，否则下载/解压到 E: 后建 junction `speech/kws_hw/data → E:\...`。runs 输出较小，留在 `kws_hw/runs*`。
- 若中文路径导致 soundfile/多进程异常：整个运行目录挪 E: 运行、小型产物拷回。

## 3. 实验设计

- **数据**：Speech Commands v0.01 官方 URL 下载（~1.5GB）→ prepare_data.py 生成 12 类特征；核验 (21470,40,98)/(3096)/(3307)、meta.json 类别表、stats.npz 仅来自训练集。
- **基线**：`train.py` 默认 40 epoch（seed 42、增强开启）→ `evaluate.py`：准确率、classification report、混淆矩阵、DET、score 分布、metrics.json、misclassified.txt。先 1 epoch 冒烟再正式跑。参考区间：准确率 92~95%、EER 1.5~2.5%。
- **消融**（同测试集同评估脚本）：baseline(40ep+增强) / `--epochs 20` / `--no_augment` / `--width 48`，各独立 save_dir 分别 evaluate；汇总准确率、宏 F1、EER 对比表。
- **加分项**：`detect.py demo_long.wav --target yes --threshold 0.9`；阈值 0.5/0.9/0.99 对比成表；绘制分数-时间曲线（含阈值线与检测点）。`my_recordings/` + `scripts/rerun_infer_detect.py` 一键重跑。
- **错误分析**：misclassified.txt 取 top 置信错误 3~5 条，波形 + log-Mel 对照图 + 声学分析（元音/爆破音相似性、噪声、截断、unknown 合理错误）；如实说明基于谱图检查而非人工试听。
- **报告**：`reports/build_report.py`（python-docx），8 章结构 4~8 页，全部数字程序化读自 metrics.json/消融汇总；LibreOffice headless 转 PDF（Word COM 导 PDF 会卡）；注明教学代码来源、本人工作、CC BY 4.0 与参考文献。
- **打包**：`scripts/package_submission.py` 生成 `2023302610_肖怀瑾_kws.zip`（code/ + runs/best.pt + confusion_matrix.png + det_curve.png + training_curves.png + metrics.json + report.pdf；排除 data/ 与环境）。

## 4. 实施顺序与状态

| 阶段 | 工作 | 验收产物 | 状态 |
| --- | --- | --- | --- |
| 1 | AGENTS.md 更新、.gitignore、本计划、speech 骨架 | 文档与目录就绪 | 完成 |
| 2 | 教师代码解压与审读、环境核验与补装 | 环境检查日志、代码审读记录 | 进行中 |
| 3 | 数据下载、特征提取与核验 | data/processed 清单与核验记录 | 未开始 |
| 4 | 基线 40 epoch 训练 + 评估 | runs/ 产物、metrics.json | 未开始 |
| 5 | 消融三组 + 汇总表 | 消融对比 JSON/表 | 未开始 |
| 6 | 长音频检测、阈值实验、自录入口 | 检测结果与曲线图 | 未开始 |
| 7 | 错误分析素材 | 谱图对照与条目分析 | 未开始 |
| 8 | 报告 docx→PDF、README、打包、阶段提交 | report.pdf、提交 zip、Git 提交 | 未开始 |

## 5. 验收清单

- [ ] 数据 21470/3096/3307 与 12 类核验
- [ ] 测试准确率 92~95%、EER 1.5~2.5% 区间核对
- [ ] 训练曲线、混淆矩阵、DET、分数分布、结果表、消融表齐备
- [ ] 消融 4 组完成且同测试集可比
- [ ] 加分项：长音频检测 + 阈值实验完成
- [ ] 自录入口就绪 + 重跑脚本；用户录音后补跑并更新报告（当前如实标注）
- [ ] 报告 PDF 4~8 页、数字与 metrics.json 一致
- [ ] 提交 zip 命名与内容符合指导文档 10.4 节
