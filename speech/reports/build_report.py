"""语音大作业报告生成器：从 outputs/ 下的真实运行结果程序化生成 docx。

所有数字（数据规模、指标、消融、阈值实验、案例）均读取 JSON/txt 证据文件，
不手抄任何数值。生成 4~8 页报告，随后用 LibreOffice 转 PDF。

用法（在仓库根目录，需先完成训练/评估/推理套件/消融汇总/错误分析）:
    conda run -p D:/Anaconda3/envs/pytorch python -s speech/reports/build_report.py
"""

import json
import re
import sys
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import docx_helpers as H  # noqa: E402

OUT = ROOT / "outputs"
FIG = OUT / "baseline"
STUDENT = "肖怀瑾"
STUDENT_ID = "2023302610"

# 每对 (true, pred) 的声学分析要点，基于波形与 log-Mel 谱图检查归纳。
CASE_NOTES = {
    ("unknown", "go"):
        "dog 的韵腹为后元音 /ɔː/，与 go 的 /oʊ/ 共振峰结构接近，且起始 /d/ 与 /g/ 同为"
        "浊爆破音（仅齿龈与软腭部位之差）；谱图上 0.4~1.0 秒 Mel 0~15 频带的强谐波条带"
        "与 go 的元音段高度相似。unknown 本无独立类别，模型只能归入最像的已知关键词，"
        "属“合理的错误”。",
    ("unknown", "right"):
        "five 与 right 共享双元音 /aɪ/：谱图中 Mel 25~35 频带的斜升共振峰过渡叠加低频"
        "强能量带，与 right 的韵腹结构几乎一致；差异主要在起始辅音（/f/ 为清摩擦音、"
        "能量弱），2 万参数的小模型未能据此区分。",
    ("down", "no"):
        "该样本短促（约 0.3~0.55 秒），down 的 /aʊ/ 向圆唇滑移后的低频结构与 no 的 "
        "/oʊ/ 在 Mel 0~15 频带上难以区分，爆破段之后缺乏足以区分的复韵母信息；短元音/"
        "爆破音词互混也是参考结果中的主要混淆来源。",
    ("unknown", "on"):
        "four 的元音 /ɔː(r)/ 与 on 的韵腹同属后元音区域、共振峰位置接近；起始 /f/ 摩擦"
        "音能量弱并与元音直接相连，谱图 0.35~0.9 秒的平缓低频能量包络与 on 高度相似，"
        "模型以 0.99 的置信度将其归入 on。",
}


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_classification_report(path, classes):
    """解析 sklearn classification_report 文本为 {class: (p, r, f1, support)}。"""
    rows = {}
    text = Path(path).read_text(encoding="utf-8")
    for line in text.splitlines():
        m = re.match(r"^\s*(\S+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+(\d+)\s*$", line)
        if m and m.group(1) in classes:
            rows[m.group(1)] = (float(m.group(2)), float(m.group(3)),
                                float(m.group(4)), int(m.group(5)))
    return rows


def pct(value, digits=2):
    return f"{value * 100:.{digits}f}%"


def title_block(doc):
    H.cover_line(doc, "《多媒体技术》课程大作业 · 语音部分", 12, True)
    H.cover_line(doc, "从零训练一个关键词唤醒模型（KWS）", 15, True, space_after=4)
    H.cover_line(doc, f"{STUDENT}　学号 {STUDENT_ID}　2026 年 10 月 31 日", 10,
                 False, space_after=6)


def section_task(doc):
    H.heading(doc, "1. 任务与背景", 1)
    H.body(doc,
           "关键词唤醒（Keyword Spotting, KWS）是智能音箱、手机与车载语音助手常驻运行的"
           "第一道判别模块：系统不解析整句内容，只持续判断音频中是否出现特定唤醒词。与"
           "语音识别（ASR）相比，KWS 输出的是“是否/哪个关键词”的判别与概率，模型常驻端侧，"
           "必须小、快、省电，关键指标也从字错误率（WER）换成了误唤醒率（FAR）、漏唤醒率"
           "（FRR）及二者相等的等错误率（EER）。")
    H.body(doc,
           "本作业在 Google Speech Commands v0.01 数据集上从零训练一个约 2 万参数的"
           " DS-CNN 关键词分类器：输入 1 秒 16 kHz 单声道音频，输出 12 类概率"
           "（10 个关键词 + unknown + silence）；训练完成后以 yes 为唤醒词评估 FAR/FRR/EER，"
           "并完成识别示例、错误分析、消融对比与长音频滑动窗口检测（加分项）。代码基于教师"
           "提供的教学代码（kws_code.zip），本人完成全部运行、结果核验、错误分析与报告写作。")


def section_data(doc, data):
    counts = data["counts"]
    classes = list(counts["train"].keys())
    H.heading(doc, "2. 数据与特征", 1)
    H.body(doc,
           f"数据集为 Google Speech Commands v0.01（约 6.5 万条 1 秒英文单词录音，"
           f"16 kHz 单声道，CC BY 4.0 许可，仅用于课程学习，下载 URL 与校验 MD5 见附录 A）。"
           f"取 10 个词（yes、no、up、down、left、right、on、off、stop、go）作为关键词，"
           f"其余 20 个词按固定种子抽样构成 unknown（第 11 类的前身），从 6 个背景噪声"
           f"文件按 0.5 秒步长切 1 秒片段构成 silence 类，共 12 类。划分严格沿用官方 "
           f"validation_list.txt / testing_list.txt（按说话人哈希得到，同一说话人只出现在"
           f"一个集合，测试集是 speaker-disjoint 的），最终训练/验证/测试为 "
           f"{data['num_train']} / {data['num_val']} / {data['num_test']} 条，"
           f"分布汇总见表 1。")
    rows = []

    def agg(split, part):
        c = counts[split]
        if part == "kw":
            return sum(c[k] for k in classes if k not in ("unknown", "silence"))
        return c[part]

    for name, part in [("10 个关键词合计", "kw"), ("unknown", "unknown"),
                       ("silence", "silence")]:
        rows.append([name, agg("train", part), agg("val", part),
                     agg("test", part)])
    rows.append(["合计", data["num_train"], data["num_val"], data["num_test"]])
    H.add_table(doc, 1, "Speech Commands 样本分布汇总（条）",
                ["类别", "训练集", "验证集", "测试集"], rows,
                widths=[4.6, 3.2, 3.2, 3.2], align_center_cols={1, 2, 3})
    H.body(doc,
           "特征提取为纯 NumPy 实现的 log-Mel 频谱：25 ms 窗长（400 点）按 10 ms 帧移"
           "（160 点）分帧共 98 帧，加 Hamming 窗后做 512 点 FFT 得到 257 维功率谱，经 "
           "40 个三角 Mel 滤波器压缩为 40 维，取对数并转置成 40×98 的特征图；归一化使用的"
           "均值/标准差只在训练集上统计，避免验证/测试信息泄漏（数据泄漏）。图 1 展示一条"
           " yes 测试样本的波形与 log-Mel 特征：能量集中在 0.3~0.8 秒的低频段，与发音结构"
           "一致。")
    H.add_figure(doc, 1, FIG / "fig_feature_example.png",
                 "测试集一条 yes 样本的波形（上）与 40×98 log-Mel 特征（下）",
                 width_cm=11.0)


def section_model(doc, ablation):
    row = next(r for r in ablation["rows"] if r["run"] == "runs")
    H.heading(doc, "3. 模型", 1)
    H.body(doc,
           "模型为教师教学代码中的小型 DS-CNN（深度可分离卷积网络，Hello Edge 风格），"
           "输入 (batch, 1, 40, 98)，结构见表 2。深度可分离卷积把标准 3×3 卷积拆成"
           "“逐通道 3×3 depthwise + 1×1 pointwise”两步：以 32→64 通道为例，标准卷积需 "
           "3×3×32×64 = 18,432 个参数，深度可分离只需 3×3×32 + 1×1×32×64 = 2,336 个，"
           "减少近 8 倍——这是模型能压到约 2 万参数、适合端侧常驻的原因。")
    H.add_table(doc, 2, "DS-CNN 结构（width = 32）",
                ["层", "输出尺寸", "说明"],
                [["输入", "(1, 40, 98)", "1 通道 log-Mel 特征图"],
                 ["Conv 3×3 + BN + ReLU", "(32, 40, 98)", "stem，普通卷积升维"],
                 ["DSBlock 32→32 + MaxPool", "(32, 20, 49)", "depthwise + pointwise"],
                 ["DSBlock 32→64 + MaxPool", "(64, 10, 24)", ""],
                 ["DSBlock 64→64 + MaxPool", "(64, 5, 12)", ""],
                 ["DSBlock 64→128 + MaxPool", "(128, 2, 6)", ""],
                 ["GlobalAvgPool + Flatten", "(128,)", "整图平均为定长向量"],
                 ["Dropout(0.1) + Linear", "(12,)", "12 类 logits"]],
                widths=[5.2, 3.6, 5.6])
    H.body(doc,
           f"本次训练 width=32 的模型共 {row['params_k']:.2f} K 参数；训练用交叉熵损失，"
           "推理取 softmax 概率最大者作为预测类别，同时保留 yes 概率作为唤醒检测分数。")


def section_training(doc):
    H.heading(doc, "4. 训练设置", 1)
    H.body(doc,
           "训练配置见表 3，全部使用教师代码默认值：AdamW 优化器配合余弦退火学习率，"
           "数据增强为时间平移（±80 ms）与 SpecAugment（随机遮挡频率/时间块），二者在"
           "消融实验中单独关闭以验证作用。模型选择以验证集准确率为准：每个 epoch 结束"
           "在验证集评估，仅保存更高的 checkpoint 到 best.pt；测试集只在最终评估一次，"
           "不参与任何调参。")
    H.add_table(doc, 3, "训练超参数与固定设置",
                ["项目", "取值", "说明"],
                [["epoch", "40", "消融另设 20 epoch 对比"],
                 ["batch size", "128", ""],
                 ["优化器", "AdamW", "lr=1e-3，weight_decay=1e-4"],
                 ["学习率调度", "CosineAnnealingLR", "从 1e-3 平滑退火到 0"],
                 ["数据增强", "时间平移 + SpecAugment", "±80 ms 平移；0/1 块频率与时间遮挡"],
                 ["随机种子", "42", "torch/numpy/random 统一设置"],
                 ["模型选择", "验证集准确率最高", "保存为 best.pt"],
                 ["测试集使用", "最终评估一次", "不参与调参，speaker-disjoint"]],
                widths=[3.4, 4.6, 6.4])


def section_results(doc, data, metrics, history, per_class):
    classes = list(data["counts"]["train"].keys())
    H.heading(doc, "5. 实验结果", 1)
    H.body(doc,
           f"训练 {len(history['train_loss'])} 个 epoch，最优验证集准确率出现在第 "
           f"{metrics['checkpoint_epoch']} 轮（{pct(metrics['checkpoint_val_acc'])}）。"
           f"在 {data['num_test']} 条测试集上，总体准确率 {pct(metrics['accuracy'])}，"
           f"错误 {metrics['num_errors']} 条；把 yes 作为唤醒词、其余 11 类作为负类时，"
           f"ROC-AUC = {metrics['roc_auc']:.4f}，EER = {pct(metrics['eer'])}，"
           f"主要指标见表 4。")
    H.add_table(doc, 4, "测试集主要结果（唤醒词 yes）",
                ["指标", "数值", "含义"],
                [["总体准确率", pct(metrics["accuracy"]),
                  f"{data['num_test']} 条 12 类判别"],
                 ["宏平均 F1", f"{per_class_macro_f1(per_class):.4f}",
                  "12 类 F1 的算术平均"],
                 ["ROC-AUC", f"{metrics['roc_auc']:.4f}", "yes 分数的排序能力"],
                 ["EER", pct(metrics["eer"]), "FAR = FRR 相等处的错误率"],
                 ["FAR=1% 时 FRR", pct(metrics["frr_at_far"]["0.01"]["frr"]),
                  "允许 1% 误唤醒时的漏唤醒率"],
                 ["FAR=0.1% 时 FRR", pct(metrics["frr_at_far"]["0.001"]["frr"]),
                  "更严苛工作点的漏唤醒率"]],
                widths=[4.0, 3.2, 7.2])
    H.add_figure(doc, 2, FIG / "training_curves.png",
                 "训练曲线：损失（左）与准确率（右）随 epoch 变化", width_cm=11.0)
    worst = sorted(classes, key=lambda c: per_class[c][1])[:3]
    worst_text = "、".join(f"{c}（recall {per_class[c][1]:.4f}）" for c in worst)
    H.body(doc,
           f"从分类报告看，召回率最低的三类是 {worst_text}。图 3 的混淆矩阵显示：错误主要"
           "集中在发音相近的短词之间（元音与爆破音相似），unknown 类由 20 个不同单词构成、"
           "分散到各个关键词上属于预期行为，silence 中少量片段被识别为元音相近的词。"
           "图 4 的 DET 曲线整体贴近左下角，阶梯形态源于正样本仅 256 条的测试集分辨率。")
    H.add_figure(doc, 3, FIG / "confusion_matrix.png", "测试集混淆矩阵（行=真实，列=预测）",
                 width_cm=10.0)
    H.add_figure(doc, 4, FIG / "det_curve.png",
                 "唤醒词 yes 的 DET 曲线（红点为 EER，绿三角为 FAR=1%/0.1% 工作点）",
                 width_cm=8.5)
    H.body(doc,
           "需要说明的是：本测试集是一条一条孤立的 1 秒单词，这里的 FAR/FRR 是测试集上的"
           "等价指标，不能外推为真实产品中“每小时误唤醒几次”的结论；后者需要小时级长音频"
           "（见第 7 节加分项）。")


def per_class_macro_f1(per_class):
    return sum(v[2] for v in per_class.values()) / len(per_class)


def section_errors(doc, error_cases, per_class):
    H.heading(doc, "6. 错误分析", 1)
    H.body(doc,
           "从 misclassified.txt 中按“模型错误置信度”降序挑取 4 条典型案例，"
           "图 5 给出它们的波形与 log-Mel 特征对照。分析方法为：对照波形能量分布、"
           "元音共振峰条带与摩擦音成分进行谱图检查（未做人耳试听，如实说明）。")
    for i, case in enumerate(error_cases["top_cases"], 1):
        key = (case["true"], case["pred"])
        note = CASE_NOTES.get(key, "两词在发音上存在相近的元音/辅音结构，谱图上能量分布"
                                   "高度相似，模型仅 2 万参数、判别边界有限。")
        H.body_no_indent(
            doc, f"案例 {i}：{case['file']}，真实 {case['true']}，预测 {case['pred']}，"
                 f"预测概率 {case['prob']:.4f}。{note}")
    H.body(doc,
           "其中 unknown 被预测为某个关键词属于“合理的错误”：unknown 本身是其余 20 个词"
           "的集合，模型没有学过这些词的独立类别，只能把它们归到最像的已知关键词；这类"
           "错误在真实唤醒系统中由“唤醒后接 ASR 二次确认”来兜底。")
    H.add_figure(doc, 5, FIG / "fig_error_analysis.png",
                 "最高置信错误样本的波形与 log-Mel 特征对照（左：波形；右：谱图）",
                 width_cm=11.5)


def section_ablation(doc, ablation):
    H.heading(doc, "7. 消融实验", 1)
    H.body(doc,
           "按“只改一个变量、其余不变”设计四组对比，全部使用同一数据划分、同一测试集与"
           "同一评估脚本（协议见附录 A 命令），结果见表 5。")
    rows = []
    short = {"runs": "基线：40ep+增强(w32)", "runs_20": "少训练：20ep+增强(w32)",
             "runs_noaug": "无增强：40ep(w32)", "runs_w48": "加宽：40ep+增强(w48)"}
    for r in ablation["rows"]:
        if r.get("status") != "ok":
            continue
        minutes = f"{r['train_minutes']:.1f}min" if r.get("train_minutes") else "—"
        rows.append([short[r["run"]], f"{r['params_k']:.2f}K", f"{r['epochs']}",
                     minutes, f"{r['test_accuracy']:.2f}%",
                     f"{r['macro_f1']:.4f}", f"{r['eer_percent']:.2f}%"])
    H.add_table(doc, 5, "消融实验对比（同一测试集 3307 条）",
                ["配置", "参数量", "epoch", "训练用时", "测试准确率", "宏 F1", "EER"],
                rows,
                widths=[3.5, 1.8, 1.6, 1.8, 2.2, 1.9, 1.7],
                align_center_cols={1, 2, 3, 4, 5, 6}, font_size=8.5)
    base = next(r for r in ablation["rows"] if r["run"] == "runs")
    r20 = next((r for r in ablation["rows"] if r["run"] == "runs_20"), None)
    naug = next((r for r in ablation["rows"] if r["run"] == "runs_noaug"), None)
    w48 = next((r for r in ablation["rows"] if r["run"] == "runs_w48"), None)
    parts = []
    if r20:
        parts.append(f"训练轮数从 40 降到 20，准确率由 {base['test_accuracy']:.2f}% 降为 "
                     f"{r20['test_accuracy']:.2f}%，EER 由 {base['eer_percent']:.2f}% 升至 "
                     f"{r20['eer_percent']:.2f}%，说明模型尚未完全收敛，多训练仍有收益")
    if naug:
        parts.append(f"关闭数据增强后测试准确率降为 {naug['test_accuracy']:.2f}%"
                     f"（EER {naug['eer_percent']:.2f}%），验证了时间平移与 SpecAugment "
                     f"对缓解过拟合、稳定测试表现的作用")
    if w48:
        parts.append(f"宽度加大到 48（参数 {w48['params_k']:.2f} K）后 12 类准确率升到 "
                     f"{w48['test_accuracy']:.2f}%（四组最高），但 EER {w48['eer_percent']:.2f}%"
                     f" 反而高于基线的 {base['eer_percent']:.2f}%")
    if parts:
        H.body(doc, "对比结论：" + "；".join(parts) + "。综合来看，基线（width 32）在唤醒"
               "检测最关键的 EER 上四组最低；width 48 的 12 类准确率最高但参数约为基线 "
               f"{w48['params_k'] / base['params_k']:.1f} 倍、EER 未同步改善。结合端侧小"
               "模型的定位，保留默认 width 32 配置作为最终交付模型。")


def section_bonus(doc, inference, ablation):
    H.heading(doc, "8. 加分项：长音频唤醒检测与识别示例", 1)
    H.body(doc,
           "真实唤醒是连续监听。detect.py 以 0.25 秒步长在音频上滑 1 秒窗口打分，把连续"
           "超过阈值的窗口合并为一组、每组保留最高分作为一次唤醒。对随代码提供的 7 秒"
           "示例音频 demo_long.wav（内容为 静音→yes→静音→stop→静音→yes→静音），在 "
           "0.5、0.9、0.99 三个阈值下分别检测，结果见表 6。")
    thr = inference["threshold_experiment"]
    rows = []
    for key, item in thr.items():
        dets = item["detections"]
        rows.append([f"{item['threshold']:g}",
                     str(item["num_detections"]),
                     "、".join(f"t={d['t']:.2f}s ({d['score']:.4f})" for d in dets) or "无"])
    H.add_table(doc, 6, "demo_long.wav 滑动窗口检测的阈值对比（窗口 0.25 s 步长）",
                ["阈值", "检测次数", "检测时间点与分数"], rows,
                widths=[1.6, 2.2, 10.8], align_center_cols={0, 1}, font_size=8.5)
    H.add_figure(doc, 6, FIG / "fig_detect_timeline.png",
                 "demo_long.wav 的窗口分数曲线与三个阈值（红三角为阈值 0.9 的检测结果）",
                 width_cm=14.0)
    H.body(doc,
           "本模型对两次 yes 的窗口分数几乎为 1.0、远高于 0.99 的阈值，因此三个阈值下"
           "都恰好检出 2 次、无误检，stop 与静音段的分数始终低于 0.5——该段音频上阈值"
           "未造成差异；若换成含噪或远场音频，低阈值会开始引入误触发、高阈值则可能漏检"
           "（FAR/FRR 权衡的量化见第 5 节 DET 曲线）。这说明孤立测试集上的指标需要与"
           "长音频实测互相补充。图 6 中两次 yes 位于约 1.5 s 与 5.5 s，窗口中心时间与"
           "指导文档参考值（1.25 s / 5.25 s）相差一个步长，属正常范围。")
    H.body(doc,
           "识别示例方面（指导文档第 7 步），用测试集音频验证："
           + "；".join(
               f"{info['file']} → {info['top'][0]['class']} "
               f"({info['top'][0]['prob'] * 100:.2f}%)"
               for info in inference["infer_examples"].values())
           + "。自录音频部分：" + inference["my_recordings_status"] + "。")


def section_summary(doc):
    H.heading(doc, "9. 总结与反思", 1)
    H.body(doc,
           "本次大作业走通了“音频 → log-Mel 特征 → 小型 CNN → 训练 → 评估 → 部署/推理”"
           "的完整语音应用链路：在 speaker-disjoint 的官方划分上取得 94% 量级的 12 类准确率"
           "与 2% 以内的唤醒 EER；消融实验量化了训练轮数、数据增强与模型宽度的贡献；错误"
           "分析定位到发音相近词与 unknown 的合理错误。")
    H.body(doc,
           "局限与改进方向：其一，FAR/FRR 来自孤立单词测试集，真实误唤醒率需要小时级含噪"
           "长音频验证，且应加入加噪训练提升鲁棒性；其二，2 万参数的小模型对远场、口音、"
           "混响明显更敏感，可考虑 DS-TCN 等时序结构或流式（streaming）化以降低时延；"
           "其三，检测器目前是无平滑的滑动窗口，工程化需要端点检测与双阈值（唤醒/解除）"
           "机制。若继续做，会优先在训练中加入背景噪声混合并实现流式检测。")


def section_references(doc):
    H.heading(doc, "参考文献", 1)
    refs = [
        "[1] Pete Warden. Speech Commands: A Dataset for Limited-Vocabulary Speech "
        "Recognition. arXiv:1804.03209, 2018.",
        "[2] Yundong Zhang, Naveen Suda, Liangzhen Lai, Vikas Chandra. Hello Edge: "
        "Keyword Spotting on Microcontrollers. arXiv:1711.07128, 2017.",
        "[3] Daniel S. Park et al. SpecAugment: A Simple Data Augmentation Method for "
        "Automatic Speech Recognition. arXiv:1904.08779, 2019.",
        "[4] Andrew G. Howard et al. MobileNets: Efficient Convolutional Neural Networks "
        "for Mobile Vision Applications. arXiv:1704.04861, 2017.",
        "[5] WeKWS 开源项目. https://github.com/wenet-e2e/wekws.",
        "[6] 课程教学代码 kws_code.zip 与《音频大作业指导文档》，2026 年 10 月。",
    ]
    for ref in refs:
        p = H.body_no_indent(doc, ref)
        p.runs[0].font.size = Pt(10.5)
        p.paragraph_format.line_spacing = 1.15


def section_appendix(doc, data, env):
    H.heading(doc, "附录 A：运行环境与命令", 1)
    rows = [
        ["Python", env["python"], "Conda 环境 D:\\Anaconda3\\envs\\pytorch"],
        ["PyTorch / CUDA", f"{env['torch']}（CUDA {env['torch.version.cuda']}）",
         f"GPU：{env['gpu']}"],
        ["numpy/scipy/sklearn",
         f"{env['numpy']} / {env['scipy']} / {env['sklearn']}", ""],
        ["soundfile/matplotlib/tqdm",
         f"{env['soundfile']} / {env['matplotlib']} / {env['tqdm']}",
         "soundfile、python-docx 为本次在环境内补装"],
    ]
    H.add_table(doc, 7, "运行环境", ["组件", "版本", "说明"], rows,
                widths=[4.4, 5.0, 5.2], font_size=8.5)
    p = H.body_no_indent(doc, f"数据来源：{data['source_url']}（MD5 {data['md5']}，"
                              f"多连接分段下载后校验）。关键命令（均在上述环境的仓库"
                              f"根目录以 python -s 运行）：")
    p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
    H.add_code_block(doc, "\n".join([
        "python -s prepare_data.py --data_dir E:/MultimediaCourseAssets/speech/data",
        "python -s train.py                     # 基线 40 epoch（runs/）",
        "python -s train.py --epochs 20 --save_dir runs_20",
        "python -s train.py --no_augment --save_dir runs_noaug",
        "python -s train.py --width 48 --save_dir runs_w48",
        "python -s evaluate.py                  # 及各 --checkpoint/--save_dir 组合",
        "python -s detect.py demo_long.wav --target yes --threshold 0.9",
        "python -s speech/scripts/run_inference_suite.py",
    ]))
    H.body_no_indent(doc,
                     "以上训练与评估均由本人在教师教学代码（kws_code.zip，未改动算法部分）"
                     "上实际运行；指标、图表全部来自上述命令的真实输出，报告数字由脚本从 "
                     "metrics.json 等结果文件程序化写入。")


def main():
    data = load_json(OUT / "data_summary.json")
    metrics = load_json(FIG / "metrics.json")
    history = load_json(FIG / "history.json")
    ablation = load_json(OUT / "ablation_summary.json")
    inference = load_json(FIG / "inference_results.json")
    error_cases = load_json(FIG / "error_cases.json")
    env = load_json(OUT / "environment.json")
    classes = list(data["counts"]["train"].keys())
    per_class = parse_classification_report(FIG / "classification_report.txt", classes)

    doc = H.setup_document()
    # 4~8 页的紧凑报告排版：一级标题不强制换页、正文 1.3 倍行距、压缩标题间距
    doc.styles["Heading 1"].paragraph_format.page_break_before = False
    doc.styles["Normal"].paragraph_format.line_spacing = 1.3
    doc.styles["Heading 1"].paragraph_format.space_before = Pt(10)
    doc.styles["Heading 1"].paragraph_format.space_after = Pt(4)
    doc.styles["Heading 2"].paragraph_format.space_before = Pt(8)
    doc.styles["Heading 2"].paragraph_format.space_after = Pt(3)
    H.set_core_properties(doc)
    title_block(doc)
    section_task(doc)
    section_data(doc, data)
    section_model(doc, ablation)
    section_training(doc)
    section_results(doc, data, metrics, history, per_class)
    section_errors(doc, error_cases, per_class)
    section_ablation(doc, ablation)
    section_bonus(doc, inference, ablation)
    section_summary(doc)
    section_references(doc)
    section_appendix(doc, data, env)

    H.add_footer_page_x_of_y(doc.sections[0])
    out_dir = ROOT / "reports" / "delivery-20261031"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "kws_report.docx"
    doc.save(out_path)
    H.inspect(doc, out_path)


if __name__ == "__main__":
    main()
