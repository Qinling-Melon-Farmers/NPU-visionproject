"""Body sections for the multimedia vision report."""
from __future__ import annotations

import csv
import json
from pathlib import Path

from docx.shared import Cm, Pt

from docx_helpers import (
    add_figure,
    add_table,
    body,
    body_no_indent,
    bullet,
    caption,
    heading,
)

T_OVERVIEW = 1
T_ENV = 2
T_DATA = 3
T_IMGCONF = 4
T_IMGMET = 5
T_IMGCI = 6
T_VIDSRC = 7
T_VISCONF = 8
T_VIDMET = 9
T_VIDQ = 10
T_SUMTIME = 11
T_SUMBUD = 12
T_SEG5 = 13
T_SEG10 = 14
T_SEG15 = 15
T_EXPORT = 16

F_METHOD = 1
F_FULLBEST = 2
F_FULLWORST = 3
F_SPARSEBEST = 4
F_SPARSEWORST = 5
F_VIDEO = 6
F_Q1 = 7
F_Q2 = 8
F_HEATR = 9
F_HEATD = 10
F_SUM = 11
F_SEG5 = 12
F_SEG10 = 13
F_SEG15 = 14

METHOD_ZH = {"gem": "GeM", "avg": "平均池化", "max": "最大池化"}
GALLERY_ZH = {"full": "主图库", "sparse": "稀疏图库"}


def fmt(value: float, digits: int = 4) -> str:
    return f"{value:.{digits}f}"


def add_abstract(doc, ctx):
    heading(doc, "摘要", 1)
    image = ctx["image"]
    video = ctx["video"]
    summary = ctx["summary"]
    image_main = next(m for m in image["methods"] if m["gallery"] == "full" and m["method"] == "gem")
    image_max = next(m for m in image["methods"] if m["gallery"] == "full" and m["method"] == "max")
    summary_main = next(r for r in summary["results"] if abs(r["budget"] - 0.15) < 1e-9)
    body(
        doc,
        "本文完成 GeM 图像检索、ViSiL 视频检索和 DSNet 无锚框视频摘要三个实验。"
        "图像部分在 COIL-100 上以每个对象 0°、90°、180°、270° 四张图像为查询，共 400 次查询，"
        f"主图库 6,800 张。VGG16-GeM 的平均 P@5 为 {image_main['mean_p_at_5']:.4f}，mAP 为 {image_main['map']:.4f}；"
        f"在同一骨干上换成最大池化后 mAP 为 {image_max['map']:.4f}，GeM 与最大池化的配对差异区间包含零。",
    )
    body(
        doc,
        "视频部分把 TVSum 的 10 段原视频改编成 20 个查询、90 个候选的近重复检索任务。"
        f"完整 ViSiL 和去掉视频比较 CNN 的对照都取得 20/20 的 Top-3 命中，mAP 均为 {video['metrics']['mAP']:.4f}。"
        "在这个受控任务上，两种方法没有拉开差距，结果更多说明任务本身容易，而不是两个模型等价。",
    )
    body(
        doc,
        f"摘要部分在 TVSum 的 AwmHb44_ouw（10,597 帧）上运行 DSNet AF。15% 预算选中 {summary_main['selected_frames']:,} 帧，"
        f"实际比例 {summary_main['ratio'] * 100:.4f}%，相对 20 个人工摘要的平均 F1 为 {summary_main['avg_f1']:.4f}；"
        f"同样分段的随机片段基线为 {summary['random_baseline']['mean_f1']:.4f}±{summary['random_baseline']['std_f1']:.4f}。"
        "三个实验的结论都限定在本次数据划分、受控编辑和单视频案例内。",
    )
    paragraph = doc.add_paragraph()
    run = paragraph.add_run("关键词：")
    from docx_helpers import _set_run_fonts

    _set_run_fonts(run, "黑体", 12, True)
    run = paragraph.add_run("图像检索；GeM；视频检索；ViSiL；视频摘要；DSNet")
    _set_run_fonts(run, "宋体", 12)


def add_intro(doc, ctx):
    heading(doc, "1 引言", 1)
    heading(doc, "1.1 三个任务与课程要求", 2)
    body(
        doc,
        "图像检索和视频检索都在回答“哪些内容和查询相似”，区别在输入的时间结构。图像检索把一张图映射成描述子，"
        "按相似度排序；视频检索要比较两段视频的帧序列，时间错位、剪辑和重复镜头都会改变结果。视频摘要不问“哪里相似”，"
        "它要从完整视频里挑出一部分帧，输出一个仍按原时间顺序排列的子集。三个任务的标签、指标和失败方式不同，"
        "一个任务的分数不能拿来推断另一个任务。",
    )
    body(
        doc,
        "课程任务书要求每个实验交代数据来源、规模、划分和评价标准，展示真实运行结果，并选一个案例解释成功或失败的原因。"
        "课件补充了两点：新代码和修改由编程大模型生成，学生负责提出需求、运行程序、核对结果；完整的可见交互记录放入 Word 附录。"
        "本报告按这三个要求组织，正文写方法和结果，附录保留逐查询数据、运行记录和交互原文。",
    )
    heading(doc, "1.2 数据与预训练资源", 2)
    body(
        doc,
        "图像实验使用哥伦比亚大学公开的 COIL-100。它包含 100 个对象，每个对象在转台上每隔 5° 拍一张，共 7,200 张 128×128 图像。"
        "视频实验使用 TVSum 的原始视频。TVSum 原本用于视频摘要，每段视频带 20 位标注者的逐帧重要性评分；"
        "本实验只取原视频，重新切查询和候选，把它改造成近重复检索任务。摘要实验同样使用 TVSum，但只选一段完整视频，"
        "配套作者提供的 GoogLeNet 特征和 DSNet AF 权重。",
    )
    body(
        doc,
        "三个实验都复用作者实现和预训练权重，没有重新训练。GeM 使用 cnnimageretrieval-pytorch 的 VGG16-GeM 检索权重，"
        "ViSiL 使用 PyTorch 分支的完整视频对推理权重，DSNet 使用 anchor-free 的 TVSum checkpoint。"
        "作者仓库的提交号、许可证、权重和数据的 SHA256 记在 vision/manifests 与 vision/vendor/README.md。",
    )
    heading(doc, "1.3 本人工作与报告结构", 2)
    body(
        doc,
        "本人提出数据选择、环境隔离、运行与验收要求，执行三个实验命令，核对指标、图表和导出文件，完成报告写作与排版。"
        "新增和修改的代码由编程大模型按这些要求生成；作者实现、预训练权重和公开数据来自上述来源。"
        "报告第 2 章说明环境、数据和复现方式，第 3 至 5 章分别写三个实验，第 6 章讨论三个任务的差异和局限，"
        "第 7 章给出结论，附录 A 至 D 保存逐查询结果、运行与修正记录、学生与编程大模型的交互原文，以及代理协作记录。",
    )
    add_table(
        doc,
        T_OVERVIEW,
        "三个实验的输入、主方法、对照与验收要点",
        ["实验", "独立输入", "主方法", "研究对照", "核心验收"],
        [
            ["图像检索", "COIL-100 图像", "VGG16-GeM", "同一检索骨干替换平均/最大池化", "Top-5、逐查询 P@5、平均 P@5"],
            ["视频检索", "TVSum 原视频构造的查询和候选", "完整非对称 ViSiL", "去掉视频比较 CNN", "Top-3、命中数、帧间矩阵"],
            ["视频摘要", "一段完整 TVSum 视频及匹配特征", "DSNet anchor-free", "预算变化、随机片段基线", "帧比例≤15%、选帧与导出一致"],
        ],
        widths=[2.6, 3.0, 2.9, 3.2, 2.9],
    )


def add_environment(doc, ctx):
    heading(doc, "2 实验环境、数据与复现", 1)
    heading(doc, "2.1 环境隔离", 2)
    body(
        doc,
        "课程代码在专用 Conda 环境 multimedia-vision 中运行，解释器为 Python 3.11.17，PyTorch 2.5.1，"
        "torchvision 0.20.1，CUDA runtime 11.8，NumPy 1.26.4，OpenCV 4.10.0，FFmpeg 4.3。"
        "显卡为 NVIDIA GeForce RTX 4060 Laptop GPU，显存 8 GB。所有 Python 命令都带 -s，"
        "并检查 sys.prefix 与配置中的 environment_prefix 一致，避免用户级包混入。",
    )
    body(
        doc,
        "最初尝试复用已有的 pytorch 环境，检查发现普通运行会加载用户级 OpenCV；禁用用户级包后，环境内 OpenCV 又出现 NumPy ABI 错误。"
        "因此新建独立环境，原环境保持不动。新环境的包来源、GPU 小矩阵运算、NumPy 转换、OpenCV、HDF5 和 FFmpeg 都经过检查，"
        "结果写在 vision/manifests/environment_validation.json。",
    )
    env = ctx["env"]
    rows = [
        ["Python", env["python"].split("|")[0].strip()],
        ["PyTorch / torchvision", f"{env['packages']['torch']['version']} / {env['packages']['torchvision']['version']}"],
        ["CUDA runtime", env["cuda"]["runtime"]],
        ["NumPy / OpenCV", f"{env['packages']['numpy']['version']} / {env['packages']['cv2']['version']}"],
        ["h5py / SciPy", f"{env['packages']['h5py']['version']} / {env['packages']['scipy']['version']}"],
        ["Matplotlib / Pillow", f"{env['packages']['matplotlib']['version']} / {env['packages']['PIL']['version']}"],
        ["FFmpeg / FFprobe", "4.3 / 4.3"],
        ["GPU", env["cuda"]["device"]],
    ]
    add_table(
        doc, T_ENV, "运行环境与关键依赖版本",
        ["项目", "版本或设备"], rows, widths=[4.6, 10.0], font_size=9,
        align_center_cols={0},
    )

    heading(doc, "2.2 数据来源、规模与划分", 2)
    body(
        doc,
        "COIL-100 的每张图像文件名带有对象号和角度，例如 obj67__270.png 表示第 67 个对象在 270° 的视图。"
        "本实验把 0°、90°、180°、270° 四个角度作为查询，共 400 张；查询文件从图库中排除。"
        "主图库是其余 6,800 张。为了观察视角覆盖变少时会发生什么，又构造了稀疏图库：每个对象取 20°、65°、110°、…、335° 共 8 张，"
        "合计 800 张，查询与图库不重叠。相关性只看对象号，同一对象的不同视角算相关，不同对象即使颜色或形状接近也算不相关。",
    )
    body(
        doc,
        "TVSum 有 50 段视频，分属 10 个类别。检索实验在每个类别中按视频 ID 顺序选第一段能完整解码、时长不少于 80 秒的视频，共 10 段源视频。"
        "每段源视频取三个 20 秒片段：q1 从 0.1D 开始，q2 从 (D−20)/2 开始，negative 取末尾 20 秒。"
        "q1 和 q2 各生成重编码、中心裁剪 80%、顶部 10% 灰条三种变体，作为候选；negative 也生成三种变体，作为同源干扰。"
        "这样得到 20 个查询和 90 个候选。相关性定义为同一源视频，且候选原时间区间与查询区间的交集至少覆盖查询时长的 80%。"
        "原查询文件不进入候选集。",
    )
    body(
        doc,
        "摘要实验选 TVSum 官方 split 0 中按数字编号排序的第一个测试视频 video_1，对应 AwmHb44_ouw.mp4。"
        "该视频 10,597 帧，29.97 fps，时长约 353.6 秒；配套 HDF5 提供 707 个采样点的 1,024 维 GoogLeNet 特征、分段和原帧映射。"
        "选择前核对了 H5、官方标注和原视频三者的帧数与评分曲线，video_1 不与训练集重叠。",
    )
    add_table(
        doc, T_DATA, "三个实验的数据来源、规模与划分",
        ["实验", "数据", "规模", "划分", "相关性/标签"],
        [
            ["图像检索", "COIL-100", "7,200 张，100 对象×72 视角", "400 查询；主图库 6,800；稀疏图库 800", "同一对象 ID"],
            ["视频检索", "TVSum 原视频", "10 源视频；20 查询；90 候选", "每源 2 查询×3 变体；3 干扰×3 变体", "同源且时间重叠≥80%"],
            ["视频摘要", "TVSum 完整视频", "AwmHb44_ouw，10,597 帧", "官方 split 0 测试视频", "20 位标注者的逐帧重要性"],
        ],
        widths=[2.8, 2.4, 3.4, 3.2, 2.8], font_size=8.5,
    )

    heading(doc, "2.3 运行入口与证据", 2)
    body(
        doc,
        "工作区入口是 python -m vision，子命令包括 prepare、image、video、summary、report 和 verify。"
        "每次运行使用独立 run-id，输出目录保存配置、命令、耗时、代码指纹、原始指标、图表和日志；已有证据的目录拒绝覆盖。"
        "正式结果在 vision/outputs/visual-20261023-fp32，早期运行 visual-20261023 保留作修正记录。",
    )
    body(
        doc,
        "三个实验分别耗时 35.75 秒、44.91 秒和 17.34 秒（不含数据准备和首次下载）。"
        "之后执行三份独立重放：图像固定 4 个查询重算描述子，视频重算两个查询的特征和 Top-3，摘要重跑三组网络输出；"
        "最后用 verify 对保存的数组、排名、标签、导出帧数和音频流做独立核对。2026-10-28 复核时 20 项单元测试通过，verify 返回 passed。",
    )
    heading(doc, "2.4 数值约定与复现", 2)
    body(
        doc,
        "首轮图像重放的 24 组 Top-5 排名一致，但批次 4 与批次 16 的分数最大差为 4.798×10⁻⁵，超过 1×10⁻⁶ 容差。"
        "原因是 cuDNN 默认允许 TF32。正式运行显式关闭 TF32、关闭 benchmark、启用确定性卷积，并把数值配置写入缓存指纹，"
        "用新的 run-id 重跑三个模型。严格 FP32 下，图像重放最大差 4.1723×10⁻⁷，视频 Top-3 与分数一致，摘要三组输出逐元素一致。",
    )
    body(
        doc,
        "缓存按输入文件、权重、预处理和数值配置的哈希隔离；数据、权重、特征缓存和摘要 MP4 不进提交包。"
        "复现时只需修改 configs/default.yaml 的 asset_root 和 environment_prefix，或通过 --config 指定新配置。"
        "完整命令和证据索引见附录 B。",
    )


def add_image(doc, ctx):
    image = ctx["image"]
    heading(doc, "3 图像检索：GeM 与池化对照", 1)
    heading(doc, "3.1 任务与原理", 2)
    body(
        doc,
        "给定查询图像 q 和图库 G，检索系统把每张图映射成向量，按相似度降序返回前 K 张。本实验的 K 取 5。"
        "相关性按对象号判断，因此同一对象的相邻视角是正样本，不同对象之间的背景、颜色和形状相似都不改变标签。"
        "这个标准比“看起来像”更严格，也更适合 COIL-100 这种转台数据。",
    )
    body(
        doc,
        "GeM 把卷积特征图每个通道的响应汇成一个数。设通道 c 的激活为 x，池化结果为 (1/|Ω| Σ x^p)^(1/p)。"
        "p=1 时是平均池化，p→∞ 时接近最大池化；本实验的 p 从预训练权重读取，为 2.9208。"
        "VGG16 输出的 512 个通道各汇成一个数，得到 512 维描述子，再做 L2 归一化。"
        "查询和图库向量的点积就是余弦相似度，按点积降序排序。",
    )
    heading(doc, "3.2 数据与划分", 2)
    body(
        doc,
        "COIL-100 的 400 个查询覆盖 100 个对象的四个正交视角。主图库保留其余全部 6,800 张，因此每个查询有 67 张同对象正样本。"
        "稀疏图库每个对象只留 8 个视角，共 800 张，每个查询的同对象正样本降到 7 张。"
        "稀疏图库同时改变了视角覆盖和相关图像数量，所以它的指标变化不能只归因于“视角更少”这一个因素。",
    )
    body(
        doc,
        "图像按作者预处理：转成 RGB，用 PIL thumbnail 把最长边限制在 362，不放大小图，因此 COIL 的 128×128 原图保持原尺寸；"
        "再按权重里的均值和标准差归一化。三个池化方法共用同一骨干、同一权重和同一预处理，只替换池化函数。"
        "这检验的是推理阶段的池化替换，不是三个独立训练方法的公平比较。",
    )
    heading(doc, "3.3 方法", 2)
    body(
        doc,
        "主方法加载 retrievalSfM120k-vgg16-gem 权重，去掉 VGG16 最后的 max-pool，按权重结构重建卷积骨干，严格加载 features 参数。"
        "池化参数 p 从权重读取，不额外白化，单尺度推理。平均池化和最大池化沿用同一个检索训练过的骨干，只把 GeM 换成对应池化。"
        "这样可以把差异压在池化方式上，但不能回答“如果三个方法各自训练会怎样”。",
    )
    model = image["model"]
    add_table(
        doc, T_IMGCONF, "GeM 图像检索的模型与预处理配置",
        ["项目", "配置"],
        [
            ["权重", model["name"]],
            ["来源", model["source"]],
            ["作者代码提交", model["author_code"] + " @" + model["author_commit"][:12]],
            ["描述子维度", str(model["dimension"])],
            ["GeM 参数 p", f"{model['p']:.4f}（随权重）"],
            ["预处理", "RGB；PIL thumbnail，最长边上限 362；权重均值/标准差；L2 归一化"],
            ["相似度", "点积，降序；查询自身排除"],
            ["对照", "同一骨干替换平均池化或最大池化"],
        ],
        widths=[3.4, 11.2], font_size=9,
    )

    heading(doc, "3.4 评价指标", 2)
    body(
        doc,
        "P@5 是前五个结果中同对象图像数除以 5。每个查询的 AP 按排名累加命中位置的精确率，再除以当前图库中该对象的全部正样本数；"
        "mAP 是 400 个查询 AP 的平均。AP 的分母随图库变化，所以主图库和稀疏图库的 AP 不能直接横向比较，"
        "但同一图库内三种方法的差异可以比较。",
    )
    body(
        doc,
        "配对 bootstrap 以对象为重采样单位，保留同一对象四个查询的依赖。每次从 100 个对象中有放回抽 100 个，"
        "计算 400 个查询的平均差，重复 2,000 次，取 2.5% 和 97.5% 分位。固定种子 20261023。"
        "区间包含零时，本次数据不能排除“没有差异”。",
    )

    heading(doc, "3.5 总体结果", 2)
    rows = []
    for gallery in ("full", "sparse"):
        for method in ("gem", "avg", "max"):
            item = next(m for m in image["methods"] if m["gallery"] == gallery and m["method"] == method)
            rows.append([
                GALLERY_ZH[gallery], METHOD_ZH[method], str(item["queries"]),
                f"{item['gallery_size']:,}", f"{item['mean_p_at_5']:.4f}", f"{item['map']:.4f}",
            ])
    add_table(
        doc, T_IMGMET, "三种池化方法在 COIL-100 上的检索指标",
        ["图库", "方法", "查询数", "图库数", "平均 P@5", "mAP"],
        rows, widths=[2.4, 2.6, 2.2, 2.4, 2.6, 2.4], font_size=9,
        numeric_cols={2, 3, 4, 5}, align_center_cols={0, 1},
    )
    add_figure(
        doc, F_METHOD, ctx["figures"] / "fig01_methods.png",
        "两种图库下三种池化方法的平均 P@5 与 mAP（COIL-100，400 查询）",
    )
    body(
        doc,
        f"主图库上 GeM 的平均 P@5 为 {image['methods'][0]['mean_p_at_5']:.4f}，mAP 为 {image['methods'][0]['map']:.4f}；"
        "最大池化的 P@5 为 0.9905、mAP 为 0.7306，略高于 GeM；平均池化最低，mAP 为 0.7095。"
        "三者的 P@5 差距只有 0.003，说明在前五张里找到同对象并不难。",
    )
    body(
        doc,
        "稀疏图库把正样本数从 67 降到 7，三种方法的 P@5 都降到 0.78–0.80，mAP 反而略高于主图库。"
        "这不是模型变强了，而是图库变小、干扰变少，AP 的分母也变了。GeM 和最大池化的 P@5 都是 0.7970，"
        "最大池化的 mAP 为 0.7449，GeM 为 0.7423。两个图库上最大池化都没有输给 GeM，这一点需要如实写出来。",
    )

    heading(doc, "3.6 不确定性与配对差异", 2)
    rows = []
    for item in image["bootstrap"]:
        rows.append([
            GALLERY_ZH[item["gallery"]],
            "GeM − 平均池化" if item["contrast"] == "gem-avg" else "GeM − 最大池化",
            f"{item['p_at_5_difference']:+.4f}",
            f"[{item['p_at_5_ci95'][0]:.4f}, {item['p_at_5_ci95'][1]:.4f}]",
            f"{item['ap_difference']:+.4f}",
            f"[{item['ap_ci95'][0]:.4f}, {item['ap_ci95'][1]:.4f}]",
        ])
    add_table(
        doc, T_IMGCI, "GeM 与两种池化的配对差异及 95% 区间",
        ["图库", "对比", "ΔP@5", "95% 区间", "ΔAP", "95% 区间"],
        rows, widths=[1.8, 3.4, 1.8, 2.8, 1.8, 2.8], font_size=8.5,
        numeric_cols={2, 3, 4, 5}, align_center_cols={0, 1},
    )
    body(
        doc,
        "主图库上 GeM 相对平均池化的 AP 差为 +0.0183，区间 [0.0092, 0.0275]，没有包含零；"
        "相对最大池化的 AP 差为 −0.0028，区间 [−0.0076, 0.0022]，包含零。稀疏图库的方向相同："
        "GeM 比平均池化高 0.0194，区间 [0.0095, 0.0298]；与最大池化的差为 −0.0026，区间包含零。"
        "P@5 的区间大多跨零，说明前五命中率对池化方式不敏感。",
    )
    body(
        doc,
        "这些区间只覆盖对象重采样带来的变化，没有覆盖数据域、独立训练和超参数选择。因此可以说“在这个骨干和这次划分上，"
        "GeM 的 AP 高于平均池化”，不能说“GeM 一定优于最大池化”，也不能把结论推广到其他数据集。",
    )

    heading(doc, "3.7 案例分析", 2)
    body(
        doc,
        "图 2 和图 4 是两个图库中 P@5=1、AP 也达到 1 的查询。以主图库的 obj95__90 为例，前五张都是 obj95 的不同视角，"
        "排名第一的相似度为 0.99 左右，后面几张逐渐降低。这个结果说明描述子对同一对象的视角变化比较稳。"
        "图 3 和图 5 是按 P@5 和 AP 选出的最差查询，选图规则在运行前固定，没有按模型分数挑数据。",
    )
    add_figure(doc, F_FULLBEST, ctx["figures"] / "fig_top5_full_best.png",
               "主图库最佳查询 obj95__90 的 Top-5（图像 ID 与点积相似度）")
    add_figure(doc, F_FULLWORST, ctx["figures"] / "fig_top5_full_worst.png",
               "主图库最差查询 obj67__270 的 Top-5（图像 ID 与点积相似度）")
    add_figure(doc, F_SPARSEBEST, ctx["figures"] / "fig_top5_sparse_best.png",
               "稀疏图库最佳查询 obj97__90 的 Top-5（图像 ID 与点积相似度）")
    add_figure(doc, F_SPARSEWORST, ctx["figures"] / "fig_top5_sparse_worst.png",
               "稀疏图库最差查询 obj44__90 的 Top-5（图像 ID 与点积相似度）")
    body(
        doc,
        "主图库最差的 obj67__270 是一盒白色长条包装。前两名是 obj67 的相邻视角，相似度 0.9478 和 0.9265；"
        "后三名是绿色包装 obj98，相似度 0.8878、0.8728、0.8599。两个对象的長方外形、圆形标志和中央文字布局很像，"
        "颜色差异没有阻止混淆。这个查询的 P@5=0.40，AP≈0.1321。",
    )
    body(
        doc,
        "稀疏图库最差的 obj44__90 是一把浅色带柄小铲，前五名却是 obj77 和 obj41 的浅色木制几何组合，P@5=0，AP≈0.0282。"
        "稀疏图库每个对象只剩 8 个视角，查询与正样本的视角差更大；在这种情况下，颜色和轮廓容易盖过对象身份。"
        "相似度 0.78–0.80 只能说明向量方向接近，不能当成“匹配正确”的概率。",
    )
    body(
        doc,
        "把两个图库放在一起看，失败主要出现在两类情况：同形状不同颜色，或者稀疏视角下正样本与查询的角度差太大。"
        "前者说明 GeM 描述子对颜色并不敏感，后者说明视角覆盖会影响检索。由于稀疏图库同时改变了正样本数量和视角，"
        "这里只能把两种因素一起讨论，不能单独归因。",
    )
    body(
        doc,
        "两个图库的 GeM 查询中，P@5 未达到 1 的记录共 223/800，其中主图库 17/400，稀疏图库 206/400。"
        "主图库的 P@5 已经接近上限，继续比较三种池化的 P@5 意义不大；稀疏图库还有明显的提升空间。"
        "这也是后面把主要分析放在 AP 和配对区间上的原因。",
    )

    heading(doc, "3.8 小结", 2)
    body(
        doc,
        "GeM 在 COIL-100 上取得了 0.9880 的平均 P@5 和 0.7278 的 mAP。它与平均池化的 AP 差异为正，"
        "与最大池化的差异区间包含零；最大池化在这次实验里略高。这个结果说明池化替换会影响排序质量，但影响幅度不大，"
        "而且和具体图库、正样本数量有关。图像实验的主要局限是数据简单、查询视角固定、没有重新训练，"
        "结论只适用于这次划分和这个预训练骨干。",
    )


def add_video(doc, ctx):
    video = ctx["video"]
    heading(doc, "4 视频检索：完整 ViSiL 与去 CNN 对照", 1)
    heading(doc, "4.1 任务与原理", 2)
    body(
        doc,
        "视频检索的输入是一段查询视频和一个候选库，输出是按相似度排序的候选。和图像检索相比，视频多了时间维度："
        "同一段内容可能被裁剪、压缩、加遮挡，帧与帧的对应关系会发生平移；不同时间的同机位画面又可能因为背景相似而被误判。"
        "本实验把 TVSum 的原视频切成 20 秒片段，构造近重复检索任务：查询和候选来自同一源视频的不同时间或不同编辑版本，"
        "相关性由源视频和时间重叠共同决定。",
    )
    body(
        doc,
        "TVSum 原本用于视频摘要，每段视频带重要性评分。这里只用原视频，不用摘要标签；把摘要数据改造成检索任务，"
        "需要重新定义查询、候选和相关性。这个改编是本实验的设计选择，结果不能直接和 TVSum 上的摘要性能比较。",
    )

    heading(doc, "4.2 数据、编辑与标注", 2)
    body(
        doc,
        "10 段源视频覆盖 TVSum 的 10 个类别，时长 98–323 秒。每段取 q1、q2 和 negative 三个 20 秒片段；"
        "q1、q2 是查询，negative 只作为同源干扰。每个片段生成三种变体：统一重编码、中心保留 80% 宽高再缩放、"
        "顶部 10% 半透明灰条。查询和候选使用相同的编码参数与编辑条件，避免把编码差异当成内容差异。",
    )
    body(
        doc,
        "相关性标签在模型打分前确定：候选与查询来自同一源视频，且候选的原时间区间与查询区间的交集至少覆盖查询时长的 80%。"
        "标签不看模型分数。原查询文件不进入候选集，避免自匹配。每个查询有 3 个相关候选（自己的三种变体）和 87 个其他候选，"
        "其中包含同源 negative 的变体，用来检验模型会不会被同机位背景骗到。",
    )
    body(
        doc,
        "准备阶段还做了视觉审查：为每段源视频和每个片段生成接触表，按 1 fps 采样检查重复镜头；"
        "疑似重复的帧对记录在 video_sources.json。审查通过后才把 visual_review_approved 置为 true，"
        "video 命令在未审查时会拒绝打分。审查的对象、日期和结论保存在清单里。",
    )
    rows = []
    for source in video["data"]["sources"]:
        rows.append([
            source["category"], source["id"], f"{source['duration']:.1f}",
            f"{source['width']}×{source['height']}", "2", "9",
        ])
    add_table(
        doc, T_VIDSRC, "TVSum 源视频清单与检索规模",
        ["类别", "源视频 ID", "时长（秒）", "分辨率", "查询数", "候选数"],
        rows, widths=[2.0, 4.4, 2.2, 2.6, 1.7, 1.7], font_size=9,
        numeric_cols={2, 4, 5}, align_center_cols={0, 1, 3},
    )

    heading(doc, "4.3 方法：完整 ViSiL", 2)
    body(
        doc,
        "ViSiL 先比较帧内区域，再比较帧与帧，最后比较两段视频。ResNet50 提取每帧的区域特征，经 PCA 白化和注意力加权；"
        "查询帧的每个区域在候选帧中找最佳匹配，匹配分数求平均，得到一对帧的相似度；所有帧对组成帧间相似度矩阵。"
        "二维卷积从矩阵里学习时间模式，Hardtanh 把分数截断到固定范围，最后沿查询到候选的方向做 Chamfer 汇聚。",
    )
    body(
        doc,
        "本实验使用作者 PyTorch 分支的完整非对称模型，symmetric=False，查询始终作为第一个输入。"
        "采样约 1 fps，每个片段实际解码 20 帧；短边 256、中心裁剪 224、RGB。每侧至少 4 帧的约束在运行时检查，"
        "不足 4 帧直接报错，不用复制帧凑数。帧顺序保留，缓存的特征也带时间顺序。",
    )
    body(
        doc,
        "去 CNN 对照复用完全相同的 ResNet50 特征、PCA、注意力和帧间矩阵，只去掉视频比较 CNN，保留 Hardtanh 和同方向 Chamfer。"
        "这样可以把“时间结构建模”单独拿出来看。对照不是另一个模型，也不是单帧余弦相似度。",
    )
    add_table(
        doc, T_VISCONF, "ViSiL 视频检索的模型与输入配置",
        ["项目", "配置"],
        [
            ["模型", "ViSiL PyTorch 分支，symmetric=False"],
            ["骨干", "ResNet50 区域特征，PCA 白化，注意力"],
            ["匹配", "区域 Chamfer → 帧间矩阵 → 2D CNN → Hardtanh → 有向 Chamfer"],
            ["采样", "约 1 fps；每片段 20 个实际解码帧；保留时间顺序"],
            ["空间预处理", "短边 256，中心裁剪 224，RGB"],
            ["对照", "相同特征和帧间矩阵，去掉 2D CNN"],
            ["权重/提交", "作者 PyTorch 分支 @5751de6"],
        ],
        widths=[3.4, 11.2], font_size=9,
    )

    heading(doc, "4.4 总体结果", 2)
    metrics = video["metrics"]
    add_table(
        doc, T_VIDMET, "视频检索总体指标（20 查询 / 90 候选）",
        ["指标", "完整 ViSiL", "去 CNN 对照"],
        [
            ["查询 / 候选", "20 / 90", "20 / 90"],
            ["Top-3 命中查询", str(metrics["successful_queries"]), str(metrics["without_cnn_successful_queries"])],
            ["Hit@3", f"{metrics['hit_at_3']:.4f}", f"{metrics['without_cnn_hit_at_3']:.4f}"],
            ["mAP", f"{metrics['mAP']:.4f}", f"{metrics['without_cnn_mAP']:.4f}"],
            ["配对 mAP 差异", "0.0000，95% 区间 [0.0000, 0.0000]", "—"],
        ],
        widths=[4.6, 5.0, 5.0], font_size=9, align_center_cols={1, 2},
    )
    add_figure(doc, F_VIDEO, ctx["figures"] / "fig06_video.png",
               "完整 ViSiL 与去 CNN 对照的 mAP（20 查询/90 候选）")
    body(
        doc,
        "两种方法都把全部相关候选排在无关候选之前，20 个查询全部命中，mAP 都是 1.0000。"
        "按源视频配对的 bootstrap 差值区间也是 [0, 0]。这不是“两个模型等价”的证据，而是任务太容易："
        "查询和它的三种变体在视觉上几乎一样，同源干扰又来自不同时间，模型很容易分开。",
    )
    body(
        doc,
        "当前任务没有暴露出完整 ViSiL 的时间建模优势。要拉开差距，需要更难的候选，比如更短的片段、更強的压缩、"
        "不同源但同场景的视频，或者跨数据集的负样本。本实验保留这个天花板结果，不根据测试分数重新挑查询或改协议。",
    )

    heading(doc, "4.5 逐查询结果", 2)
    rows = []
    for item in video["queries"]:
        top3 = "\n".join(
            f"{c['id']}（{c['score']:.4f}，{'相关' if c['relevant'] else '不相关'}）"
            for c in item["top3"]
        )
        rows.append([item["query_id"], item["source_id"], str(item["hit_at_3"]), f"{item['ap']:.4f}", top3])
    add_table(
        doc, T_VIDQ, "逐查询 Top-3 命中与 AP",
        ["查询 ID", "源视频", "Hit@3", "AP", "Top-3 候选（相似度，相关性）"],
        rows, widths=[4.0, 3.0, 1.3, 1.4, 4.9], font_size=7.5,
        numeric_cols={2, 3}, align_center_cols={1},
    )
    add_figure(doc, F_Q1, ctx["run"] / "video" / "EE-bNr36nyA_q1_query_top3.png",
               "查询 EE-bNr36nyA_q1 的 Top-3 代表帧（分数 0.9398、0.8960、0.8834）")
    add_figure(doc, F_Q2, ctx["run"] / "video" / "EE-bNr36nyA_q2_query_top3.png",
               "查询 EE-bNr36nyA_q2 的 Top-3 代表帧（分数 0.9412、0.8674、0.8555）")
    body(
        doc,
        "以 EE-bNr36nyA 的两个查询为例，q1 的前三名是 crop、overlay、reencode，分数 0.9398、0.8960、0.8834；"
        "q2 的前三名排序相同，分数 0.9412、0.8674、0.8555。三种编辑都保留了原片段的主要内容，"
        "裁剪和灰条带来的分数下降不大。20 个查询的 Top-3 全部相关，因此没有失败案例可以分析。",
    )

    heading(doc, "4.6 时间匹配结构", 2)
    body(
        doc,
        "图 9 是查询 EE-bNr36nyA_q1 与相关候选 q1_reencode 的帧间相似度矩阵，横轴候选时间，纵轴查询时间。"
        "矩阵里有连续的高值带，也有对角线以外的块状区域。前者来自查询和候选的同一段内容，后者来自查询内部重复出现的镜头，"
        "比如同一人物和木墙在片段中出现了两次。",
    )
    add_figure(doc, F_HEATR, ctx["figures"] / "fig09_heat_relevant.png",
               "相关候选的帧间相似度矩阵：查询 EE-bNr36nyA_q1 → q1_reencode")
    add_figure(doc, F_HEATD, ctx["figures"] / "fig10_heat_distractor.png",
               "同源干扰的帧间相似度矩阵：查询 EE-bNr36nyA_q1 → q2_reencode")
    body(
        doc,
        "图 10 换成同源但不同时间的 q2_reencode。矩阵右侧仍有一些较亮的区域，因为两个片段共享同一机位和背景；"
        "但高值没有形成贯穿整个查询的连续带。最终分数还要经过 2D CNN、Hardtanh 和有向 Chamfer，"
        "热图上的一个亮点不足以决定排名。把两张图放在一起看，连续的时间对应关系比零散的局部相似更有说服力。",
    )
    body(
        doc,
        "这也说明视频检索不能只看单帧相似度。单帧可能因为背景相同而高分，完整网络会把时间结构纳入判断。"
        "不过本次任务的相关候选与查询几乎同源，时间结构很容易；要检验 ViSiL 的优势，需要更难的时间错位和剪辑。",
    )

    heading(doc, "4.7 小结", 2)
    body(
        doc,
        "完整 ViSiL 在 20 查询/90 候选上取得 20/20 的 Top-3 命中和 1.0000 的 mAP，去 CNN 对照相同。"
        "结果说明当前受控任务太容易，不能用来证明完整网络优于简化对照。实验的价值在于把查询、候选、相关性、"
        "方向性打分和帧间矩阵都固定下来，并保留真实分数和热图；下一步应增加更难的负样本和时间扰动。",
    )


def add_summary(doc, ctx):
    summary = ctx["summary"]
    heading(doc, "5 视频摘要：DSNet 无锚框与帧预算", 1)
    heading(doc, "5.1 任务与原理", 2)
    body(
        doc,
        "视频摘要的目标是从完整视频里选出一组片段，按原时间顺序拼成 shorter video，并尽量保留主要内容。"
        "本实验做抽取式摘要，不生成新画面；长度约束按帧数计算，选中帧数除以原视频总帧数不得超过 15%。"
        "和检索不同，摘要没有“查询”，模型要预测每个时间位置的重要性，再在预算内选片段。",
    )
    body(
        doc,
        "DSNet 的无锚框版本为每个采样点预测三个量：重要性、中心度，以及到片段左右边界的距离。"
        "重要性与中心度相乘得到置信度，左右偏移确定候选区间。置信度归一化后用 NMS 去掉重叠过多的候选，"
        "再把分数恢复到原帧，按分段求平均，最后用背包在帧预算内选择完整片段。",
    )

    heading(doc, "5.2 输入与时间轴", 2)
    body(
        doc,
        "摘要实验使用 TVSum 的 AwmHb44_ouw，原视频 10,597 帧、29.97 fps、约 353.6 秒。"
        "配套 HDF5 提供 707 个采样点，每个点 1,024 维 GoogLeNet 特征；picks 是采样点对应的原帧号，"
        "change_points 是分段边界，n_frame_per_seg 是每段帧数，user_summary 是 20 位标注者的逐帧 0/1 摘要。",
    )
    body(
        doc,
        "官方 TVSum HDF5 没有 video_name 字段，不能按编号猜原视频。本实验用原视频帧数、官方 20 人标注和 H5 的帧数，"
        "以及 (mean_annotation−1)/4 在 picks 处与 gtscore 的逐点一致性建立映射。50 条记录都能由评分曲线唯一识别，"
        "其中 48 条帧数完全一致，video_16 和 video_39 的原片各多 1 帧，保留为未完全对齐，没有用于本次案例。"
        "video_1 对应 AwmHb44_ouw，三者都是 10,597 帧，最大分数误差约 2.4×10⁻⁸。H5 没有被修改。",
    )
    body(
        doc,
        "选择 video_1 前核对了两件事：它在官方 split 0 的 test_keys 中，不在 train_keys 中；"
        "原视频、H5 和标注的帧数、picks 范围、分段连续性一致。文件名匹配只是一项检查，时间轴和划分同样必要。",
    )
    add_table(
        doc, T_SUMTIME, "摘要输入的时间轴核验",
        ["项目", "值"],
        [
            ["视频", "AwmHb44_ouw.mp4（video_1）"],
            ["原视频帧数 / fps", "10,597 / 29.9700"],
            ["时长", "353.59 秒"],
            ["H5 采样点", "707"],
            ["特征维度", "1,024"],
            ["标注者", "20"],
            ["split", "官方 split 0，test_keys 10 个；video_1 不在 train_keys"],
            ["映射证据", "帧数、标注曲线、原视频哈希；最大分数误差 2.4×10⁻⁸"],
        ],
        widths=[3.6, 11.0], font_size=9,
    )

    heading(doc, "5.3 方法", 2)
    body(
        doc,
        "模型使用 DSNetAF('attention', 1024, 128, 8) 和作者提供的 tvsum.yml.0.pt。前向得到重要性、偏移和中心度，"
        "置信度为重要性乘中心度，除以最大值归一化。偏移经 offset2bbox 转成候选区间，裁剪到 [0, 采样点数]，"
        "四舍五入后按置信度做 NMS=0.4。保留的候选把分数写回采样点，同一位置取最大值。",
    )
    body(
        doc,
        "恢复原帧分数时，把每个采样点的分数铺到它到下一个采样点之间的帧；每个分段内求平均，"
        "再取 int(1000×mean) 作为整数价值。背包容量是 floor(原帧数×预算)，物品是完整分段，重量是分段帧数。"
        "作者旧代码用 OR-Tools，本实验用精确 0/1 动态规划替代，目标、整数化、容量和片段约束不变；"
        "小规模穷举验证了 DP 的最优性。",
    )
    body(
        doc,
        "5%、10%、15% 三种预算共享同一组模型预测，只改变容量；15% 是主验收配置，不根据测试 F1 调整。"
        "随机基线使用相同的分段和 15% 容量，种子 0–29 各随机排列一次，依次加入仍能容纳的完整片段，最后恢复时间顺序。"
        "这样可以把“模型选段”和“随便选段”放在同一预算下比较。",
    )

    heading(doc, "5.4 预算与结果", 2)
    rows = []
    for item in summary["results"]:
        rows.append([
            f"{item['budget'] * 100:.0f}%", f"{item['total_frames']:,}", f"{item['selected_frames']:,}",
            f"{item['export']['export_decoded_frames']:,}", f"{item['ratio'] * 100:.4f}%", f"{item['avg_f1']:.4f}",
            str(len(item["segments"])),
        ])
    add_table(
        doc, T_SUMBUD, "三种预算的帧数、比例与平均 F1",
        ["预算", "原帧数", "选中帧", "导出解码帧", "实际比例", "平均 F1", "片段数"],
        rows, widths=[1.5, 2.2, 2.2, 2.4, 2.3, 2.2, 1.8], font_size=9,
        numeric_cols={1, 2, 3, 4, 5, 6}, align_center_cols={0},
    )
    add_figure(doc, F_SUM, ctx["figures"] / "fig11_summary.png",
               "15% 预算下的重要性、中心度与所选片段（黄色区间）")
    body(
        doc,
        f"15% 预算选中 {summary['results'][2]['selected_frames']:,} 帧，实际比例 {summary['results'][2]['ratio'] * 100:.4f}%，"
        f"平均 F1 为 {summary['results'][2]['avg_f1']:.4f}；10% 为 {summary['results'][1]['avg_f1']:.4f}，"
        f"5% 为 {summary['results'][0]['avg_f1']:.4f}。预算越大，F1 越高，但 15% 也只到 0.68，"
        "说明模型选出的片段和 20 位标注者的平均摘要仍有差距。",
    )
    body(
        doc,
        f"随机片段基线在同样 15% 容量下的平均 F1 为 {summary['random_baseline']['mean_f1']:.4f}，"
        f"标准差 {summary['random_baseline']['std_f1']:.4f}。主配置比基线高 0.4852。"
        "这个差距说明模型不是随机选段；但随机种子的标准差不是跨视频置信区间，不能据此宣称数据集上的显著优势。",
    )
    body(
        doc,
        "TVSum 的 F1 是对 20 个人工摘要分别计算后平均。预算曲线使用固定的人工参考，参考摘要的长度会影响 precision/recall 的平衡，"
        "所以预算之间的 F1 差异不能单独解释为“选段语义更好”。单视频结果也不是数据集平均水平。",
    )

    heading(doc, "5.5 所选片段与代表内容", 2)
    body(
        doc,
        "三种预算的选段都保持原时间顺序。5% 预算选中 13 段，共 529 帧，约 17.7 秒；10% 选中 20 段，1,055 帧；"
        "15% 选中 27 段，1,585 帧。预算越大，片段越连续，中段的轮胎拆装和工具操作保留得越多。",
    )
    for item, table_no, figure_no, figure_name, label in [
        (summary["results"][0], T_SEG5, F_SEG5, "contactsheet_05.png", "5%"),
        (summary["results"][1], T_SEG10, F_SEG10, "contactsheet_10.png", "10%"),
        (summary["results"][2], T_SEG15, F_SEG15, "contactsheet_15.png", "15%"),
    ]:
        rows = [
            [str(seg["shot"]), f"{seg['first_frame']:,}", f"{seg['last_frame_inclusive']:,}",
             f"{seg['start_seconds']:.2f}", f"{seg['end_seconds_exclusive']:.2f}"]
            for seg in item["segments"]
        ]
        add_table(
            doc, table_no, f"{label} 预算所选片段的时间信息",
            ["片段", "起始帧", "末帧（含）", "开始（秒）", "结束（秒，不含）"],
            rows, widths=[1.8, 3.0, 3.2, 3.2, 3.4], font_size=8.5,
            numeric_cols={1, 2, 3, 4}, align_center_cols={0},
        )
        add_figure(doc, figure_no, ctx["run"] / "summary" / figure_name,
                   f"{label} 预算选中片段的代表帧（按原时间顺序）")
    body(
        doc,
        "本例内容是轮胎和轮辋的处理。三种预算都保留了轮胎、手部工具和部分工作台画面；15% 比 5% 多保留了中段操作和转动轮胎的过程。"
        "5% 摘要只有约 17.7 秒，动作被短片段切开，不能作为完整的维修教学。即使 15% 与人工摘要重合较高，"
        "也没有保留全部工具准备、动作过渡和口头解释；移除音轨进一步限制了叙事完整性。",
    )

    heading(doc, "5.6 导出与播放核验", 2)
    rows = []
    for item in summary["results"]:
        export = item["export"]
        rows.append([
            f"{item['budget'] * 100:.0f}%", "无", export["programmatic_decode"],
            f"{export['export_decoded_frames']:,}", f"{export['export_decoded_frames'] / export['fps']:.2f}",
            Path(export["path"]).name,
        ])
    add_table(
        doc, T_EXPORT, "摘要 MP4 的帧数、音频与本地文件",
        ["预算", "音频", "程序解码", "导出帧", "时长（秒）", "本地文件"],
        rows, widths=[1.5, 1.5, 2.2, 2.0, 2.4, 5.0], font_size=9,
        numeric_cols={3, 4}, align_center_cols={0, 1, 2},
    )
    body(
        doc,
        "三个 MP4 都用 FFmpeg 的 mpeg4 编码、yuv420p、无音轨，按选中帧的原顺序写入。导出时完整解码原视频，"
        "实际解码帧数与选中帧数不一致就报错；导出后再解码输出文件，核对帧数。"
        "播放检查用 FFplay 软件渲染器离屏、正常时钟播放，记录每一帧和退出码，并把导出帧与原片选帧做低分辨率 RGB 比对；"
        "三段的最大平均误差在 1.39–1.80 之间，低于容差 8。",
    )
    body(
        doc,
        "这项检查证明文件可解码、帧序正确、没有音频流，不等同于人工连续观看。报告保留这个边界，不把程序检查写成“看完了”。"
        "摘要 MP4 留在本地 cache/summary/visual-20261023-fp32，不作为提交文件。",
    )

    heading(doc, "5.7 评价与局限", 2)
    body(
        doc,
        "摘要保留了轮胎、工具操作和工作台等主要画面，遗漏了部分准备动作、镜头过渡和口头解释。"
        "15% 预算下 F1 为 0.6805，说明与人工摘要的平均重合度中等；5% 预算下 F1 只有 0.3978，短摘要更容易漏掉关键动作。"
        "这些数字只针对一段视频和 20 位标注者的平均参考。",
    )
    body(
        doc,
        "局限主要有四点：单视频，不能代表 TVSum 全体；使用预计算的 GoogLeNet 特征，特征质量受作者流程限制；"
        "人工摘要之间本身不一致，F1 的上限受参考选择影响；固定 15% 预算和完整片段约束会留下装不满的容量。"
        "这些限制不影响本次“选段—导出—核验”的流程，但决定了结论不能外推到其他视频类型。",
    )


def add_discussion(doc, ctx):
    heading(doc, "6 综合讨论", 1)
    heading(doc, "6.1 三个任务的差异", 2)
    body(
        doc,
        "图像检索的“相关”是同一对象，视频检索的“相关”是同源且时间重叠，视频摘要的“重要”是人工标注者认为值得保留。"
        "三个标签的来源不同，指标也不同：P@5 和 mAP 衡量排序，Hit@3 衡量首屏命中，F1 衡量选帧与人工摘要的重合。"
        "把 0.9880 的 P@5 和 0.6805 的 F1 放在一起比较大小没有意义，它们回答的是不同问题。",
    )
    body(
        doc,
        "三个实验都使用预训练模型，没有重新训练。这让我们能在有限算力下检查完整推理链，但也意味着结果受作者权重和训练域的限制。"
        "图像实验的 COIL-100 很干净，视频检索的候选几乎同源，摘要只有一段视频；这些条件让流程容易跑通，却不足以证明模型在开放域的表现。",
    )
    heading(doc, "6.2 有效性与局限", 2)
    body(
        doc,
        "图像实验的 400 个查询覆盖 100 个对象的四个视角，主图库和稀疏图库给出了两种难度。"
        "但查询角度固定，稀疏图库同时改变视角和正样本数，池化对照也没有独立训练。"
        "因此图像部分的结论应写成“在这个预训练骨干和这次划分上，GeM 的 AP 高于平均池化，和最大池化的差异不显著”。",
    )
    body(
        doc,
        "视频检索的 10 段源视频、20 个查询和 90 个候选是小规模受控实验。查询和候选来自同一源视频，编辑只有重编码、裁剪和灰条三种，"
        "负样本也多是同源不同时间。两种方法都到 1.0000，说明任务没有区分度。"
        "下一步可以加入跨源同场景、更多压缩和时长扰动，或者用 FIVR 这类更难的公开数据。",
    )
    body(
        doc,
        "摘要实验只做了一段视频，15% 预算的 F1 为 0.6805，比随机基线高，但离 1 还有距离。"
        "单视频、固定权重、固定人工参考和完整片段约束共同限制了外推。要评价 DSNet 的普遍性能，需要在 TVSum 的多个测试视频上重复同一流程，"
        "并报告均值、标准差和每段视频的失败案例。",
    )
    heading(doc, "6.3 大模型协作效率", 2)
    body(
        doc,
        "课件第 19 页把交互效率拆成需求表达、反馈与定位、验证与判断、有效迭代四个维度。"
        "本次交互中，需求表达主要集中在数据口径、环境隔离、资源位置、PyTorch 来源和附录拆分；"
        "反馈与定位依靠具体报错、日志和文件路径，例如 OpenCV 的 NumPy ABI 错误、FFmpeg 缺少 libx264、H5 没有 video_name；"
        "验证与判断体现在 20 项测试、三份重放和 verify 门禁；有效迭代体现在保留失败日志、用新 run-id 重跑，而不是覆盖旧结果。",
    )
    body(
        doc,
        "按快照统计，学生自由文本提示 9 条，结构化问答 2 批共 5 个问题，编程大模型可见回复 33 条，"
        "学生与编程大模型记录合计 46 条；代理协作记录 79 条，单独放在附录 D，不计入学生轮数。会话跨度约 1 小时 42 分，"
        "但包含下载、排队和并发任务，不能当作学生劳动时长。外部等待没有单独计时，报告不编造精确用时。",
    )
    body(
        doc,
        "交互轮数少不等于效率高，提示词多也不等于做得细。更有用的证据是每次修改后有没有重新运行、有没有核对真实输出、"
        "有没有在失败后保留原因。本次的返工主要集中在环境、编码、H5 映射、TF32 数值差异和报告排版；"
        "这些返工都留下了日志或修正记录，附录 B 按阶段列出。评分细则由教师确定，报告不给自己打分。",
    )


def add_conclusion(doc, ctx):
    heading(doc, "7 结论", 1)
    body(
        doc,
        "本文完成了三个视觉实验，并把数据、模型、运行、结果和交互记录整理成一份可复核的报告。主要结果如下。",
    )
    bullet(
        doc,
        "图像检索：COIL-100 上 400 次查询，VGG16-GeM 主图库平均 P@5=0.9880、mAP=0.7278；"
        "GeM 相对平均池化的 AP 差为正，相对最大池化的区间包含零。",
    )
    bullet(
        doc,
        "视频检索：TVSum 改编的 20 查询/90 候选任务上，完整 ViSiL 与去 CNN 对照均为 20/20 命中、mAP=1.0000；"
        "当前任务存在天花板效应，不能据此判断两个模型等价。",
    )
    bullet(
        doc,
        "视频摘要：AwmHb44_ouw 上 15% 预算选中 1,585/10,597 帧（14.9571%），平均 F1=0.6805，"
        "随机基线 0.1953±0.0769；三段 MP4 无音频、帧序与选帧一致。",
    )
    bullet(
        doc,
        "复现与证据：专用 Conda 环境、严格 FP32、三份独立重放、20 项测试和 verify 全部通过；"
        "逐查询数据、运行日志和交互原文保存在附录与本地目录。",
    )
    body(
        doc,
        "结论的边界是本次数据划分、受控编辑、单视频案例和预训练权重。图像部分可以进一步扩大对象和视角，"
        "视频检索需要更难的负样本，摘要需要在更多视频上重复。当前结果足以说明三个流程能真实跑通，"
        "也暴露了任务难度和方法差异之间的关系。",
    )


def add_references(doc, ctx):
    heading(doc, "参考文献", 1)
    refs = [
        "RADENOVIĆ F, TOLIAS G, CHUM O. Fine-tuning CNN image retrieval with no human annotation[J]. "
        "IEEE Transactions on Pattern Analysis and Machine Intelligence, 2019, 41(7): 1655-1668.",
        "KORDOPATIS-ZILOS G, PAPADOPOULOS S, PATRAS I, et al. ViSiL: fine-grained spatio-temporal video similarity learning[C]//"
        "Proceedings of the IEEE/CVF International Conference on Computer Vision. 2019: 6351-6360.",
        "ZHU W, LU J, LI J, et al. DSNet: a flexible detect-to-summarize network for video summarization[J]. "
        "IEEE Transactions on Image Processing, 2021, 30: 948-962.",
        "NENE S A, NAYAR S K, MURASE H. Columbia object image library (COIL-100)[R]. "
        "New York: Columbia University, 1996: CUCS-006-96.",
        "SONG Y, VALLMITJANA J, STENT A, et al. TVSum: summarizing web videos using titles[C]//"
        "Proceedings of the IEEE Conference on Computer Vision and Pattern Recognition. 2015: 5179-5187.",
        "GeM 作者实现与预训练资源[EB/OL]. https://github.com/filipradenovic/cnnimageretrieval-pytorch（2026-10-23 访问）.",
        "ViSiL PyTorch 分支[EB/OL]. https://github.com/MKLab-ITI/visil/tree/pytorch（2026-10-23 访问）.",
        "DSNet 作者实现[EB/OL]. https://github.com/li-plus/DSNet（2026-10-23 访问）.",
        "课程材料：学生实验任务书；多媒体实验介绍[Z]. 本地文件，2026.",
    ]
    for index, ref in enumerate(refs, 1):
        paragraph = doc.add_paragraph()
        paragraph.paragraph_format.first_line_indent = Pt(0)
        paragraph.paragraph_format.left_indent = Cm(0.0)
        paragraph.paragraph_format.space_after = Pt(3)
        run = paragraph.add_run(f"[{index}] {ref}")
        from docx_helpers import _set_run_fonts

        _set_run_fonts(run, "宋体", 10.5)
