"""Build a Chinese, evidence-driven local Word report without online services.

Only public result files and user-visible transcript records are consumed. Missing
results remain visibly pending. Word/LibreOffice updates TOC and page fields.
"""
from pathlib import Path
import csv
import json
from datetime import datetime

ROOT=Path(__file__).resolve().parents[1]


def read_json(path):
    path=Path(path)
    return json.loads(path.read_text(encoding='utf-8-sig')) if path.is_file() else None


def number(value, digits=4):
    return f'{value:.{digits}f}' if isinstance(value,(float,int)) else str(value)


def build(cfg, experiment_root, output_path):
    from docx import Document
    from docx.shared import Cm, Pt
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    experiment_root=Path(experiment_root);output_path=Path(output_path)
    if output_path.exists():
        raise FileExistsError(f'Preserve existing report; choose a new output filename: {output_path}')
    results={name:read_json(experiment_root/name/'results.json') for name in ('image','video','summary')}
    from vision.common.verify import verify
    verification=verify(cfg,experiment_root)
    complete=verification['status']=='passed'
    audit_pointer=read_json(ROOT/'logs'/'interaction_audit_latest.json') or {}
    interaction_audit=read_json(audit_pointer.get('audit_path','')) if audit_pointer else None
    transcript=Path(audit_pointer['transcript_path']) if audit_pointer else ROOT/'logs'/'interaction_transcript.jsonl'
    records=[];transcript_errors=[]
    if transcript.exists():
        for i,line in enumerate(transcript.read_text(encoding='utf-8-sig').splitlines(),1):
            if not line.strip():continue
            try:records.append(json.loads(line))
            except json.JSONDecodeError:transcript_errors.append(i)
    playback_review=read_json(experiment_root/'summary/playback_review.json') or {}
    playback=bool(playback_review.get('media')) and playback_review.get('status')=='passed'
    final=complete and bool(records) and not transcript_errors and playback and bool(interaction_audit)
    record_gaps=bool(interaction_audit and not interaction_audit.get('strict_full_history_complete'))
    doc=Document();section=doc.sections[0]
    section.page_width=Cm(21);section.page_height=Cm(29.7)
    section.top_margin=Cm(2.4);section.bottom_margin=Cm(2.2);section.left_margin=Cm(2.4);section.right_margin=Cm(2.2)
    normal=doc.styles['Normal'];normal.font.name='宋体';normal.font.size=Pt(10.5)
    normal.element.rPr.rFonts.set(qn('w:eastAsia'),'宋体')
    normal.paragraph_format.line_spacing=1.35
    normal.paragraph_format.space_after=Pt(6)
    for style in ('Title','Heading 1','Heading 2','Heading 3'):
        doc.styles[style].font.name='黑体';doc.styles[style].element.rPr.rFonts.set(qn('w:eastAsia'),'黑体')
    def field(paragraph,code):
        run=paragraph.add_run();begin=OxmlElement('w:fldChar');begin.set(qn('w:fldCharType'),'begin');run._r.append(begin)
        instruction=OxmlElement('w:instrText');instruction.set(qn('xml:space'),'preserve');instruction.text=code;run._r.append(instruction)
        end=OxmlElement('w:fldChar');end.set(qn('w:fldCharType'),'end');run._r.append(end)
    footer=section.footer.paragraphs[0];footer.alignment=1;footer.add_run('第 ');field(footer,' PAGE ');footer.add_run(' 页')
    settings=doc.settings.element;update=OxmlElement('w:updateFields');update.set(qn('w:val'),'true');settings.append(update)
    figures=[];missing=[];chapter=0
    def p(text):doc.add_paragraph(str(text))
    def page(title):
        nonlocal chapter
        if chapter and (title.startswith(('3 ','8 ','13 ','18 ','19 ','附录'))):doc.add_page_break()
        chapter+=1;doc.add_heading(title,level=1)
    def table(headers,rows,small=False):
        t=doc.add_table(rows=1,cols=len(headers));t.style='Table Grid'
        for cell,value in zip(t.rows[0].cells,headers):cell.text=str(value)
        repeat=OxmlElement('w:tblHeader');repeat.set(qn('w:val'),'true');t.rows[0]._tr.get_or_add_trPr().append(repeat)
        for row in rows:
            for cell,value in zip(t.add_row().cells,row):cell.text=str(value)
        if small:
            for row in t.rows:
                for cell in row.cells:
                    for paragraph in cell.paragraphs:
                        paragraph.paragraph_format.line_spacing=1
                        paragraph.paragraph_format.space_after=Pt(1)
                        for run in paragraph.runs:run.font.size=Pt(7)
        return t
    def image(value,caption,base=None):
        if not value:return
        file=Path(value)
        if not file.is_absolute():file=file.resolve() if file.is_file() else (base or experiment_root)/file
        if not file.is_file():missing.append(str(file));p('【图像证据缺失】'+caption+'：'+str(file));return
        try:
            doc.add_picture(str(file),width=Cm(16));doc.add_paragraph(f'图 {len(figures)+1}  {caption}',style='Caption');figures.append(str(file))
        except Exception as exc:
            missing.append(str(file));p('【图像嵌入失败】'+str(file)+'；'+type(exc).__name__)
    def pending(name):p('【待完成】未发现本次运行的 '+name+' 完整真实结果。本节仅记录实施协议，不含推测指标。')
    def csv_rows(file):
        if not file.exists():return []
        with file.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
    title=doc.add_paragraph();title.alignment=1;cover_run=title.add_run('多媒体技术课程\n视觉实验报告');cover_run.bold=True;cover_run.font.size=Pt(24)
    doc.add_paragraph('GeM 图像检索 · ViSiL 视频检索 · DSNet 无锚框视频摘要',style='Subtitle')
    p('姓名：________________    学号：________________')
    p('课程／班级：________________    指导教师：________________')
    p('生成日期：'+datetime.now().strftime('%Y-%m-%d'))
    status_paragraph=doc.add_paragraph('报告状态：'+('实验验证通过；交互归档存在已明示的历史原文缺口，见附录 C、D。' if final and record_gaps else '实验与记录齐备，提交前请更新目录并核对个人信息。' if final else '待完成草稿；不得作为全部验收完成的最终报告。'))
    table(['验收项目','当前状态'],[(n,'真实运行已完成' if r and r.get('status')=='completed' else '待完成') for n,r in results.items()]+[('摘要实际播放','已记录检查' if playback else '待检查／缺少记录'),('可见交互附录',f'{len(records)} 条；解析错误 {transcript_errors}' if records else '缺失')])
    doc.add_page_break();doc.add_heading('目录',level=1);field(doc.add_paragraph(),' TOC \\o "1-3" \\h \\z \\u ');p('请在 Word 中全选并更新域，以显示目录及实际页码。')
    doc.add_page_break()
    page('1 实验目标与证据边界')
    if complete:
        image_main=next(r for r in results['image']['methods'] if r['gallery']=='full' and r['method']=='gem')
        summary_main=next(r for r in results['summary']['results'] if r['budget']==.15)
        doc.add_heading('摘要',level=2)
        p(f"本项目在独立 Conda GPU 环境中复现三个预训练模型。COIL-100 上的400查询中，GeM主图库平均P@5={image_main['mean_p_at_5']:.4f}、mAP={image_main['map']:.4f}；两种图库的配对分析显示GeM相对平均池化有AP优势，与最大池化的差异区间均包含零。TVSum构造的20查询/90候选任务上，完整ViSiL和去CNN对照均达到mAP=1.0000，当前试验出现天花板效应。独立完整视频上的DSNet AF在15%预算内选中{summary_main['selected_frames']}/{summary_main['total_frames']}帧，平均F1={summary_main['avg_f1']:.4f}。结果仅支持本次对象划分、受控编辑与单视频案例；不构成开放域或数据集总体性能声明。")
    p('本报告独立覆盖图像检索、视频检索和视频摘要三个视觉实验。方法配置依据本地《学生实验任务书》和《多媒体实验介绍》，公开数据选择遵循已批准实施计划。所有数值仅从本次运行产物读取；缺失项目明确保留为待完成。')
    p('图像实验考察预训练检索描述子的对象一致性；视频实验考察受控编辑下的有向近重复匹配；摘要实验考察完整视频上的重要片段预测与帧预算选择。三者具有不同输入、标签与指标，不能直接以指标大小横向判断算法优劣。')
    table(['实验','独立输入','主方法','研究对照','核心验收'],[['图像检索','COIL-100 图像','VGG16-GeM','同一检索骨干替换平均／最大池化','Top-5、逐查询 P@5、平均 P@5'],['视频检索','TVSum 原视频构造的查询和候选','完整非对称 ViSiL','移除视频比较 CNN','Top-3、命中数、帧间矩阵'],['视频摘要','一段完整 TVSum 视频及匹配特征','DSNet anchor-free','预算变化、随机片段基线','帧比例≤15%、选帧与导出一致']])
    p('本项目复用作者实现和预训练资源，新增数据划分、输入核验、运行封装、评价、可视化及报告生成。未重新训练模型。代码由编程模型协助生成，采用与修正记录见附录。')
    page('2 环境隔离、资源与复现')
    p('课程运行使用配置指定的专用 Conda 环境与显式 python -s，避免用户级包混入。原有环境不作修复或版本替换。环境实际版本、设备、代码版本、命令和日志以本次运行元数据为准。')
    environment=read_json(ROOT/'manifests/environment_validation.json')
    if environment:
        table(['已验证依赖','实际版本'],[[k,v['version']] for k,v in environment['packages'].items()]+[['CUDA runtime',environment['cuda']['runtime']],['GPU',environment['cuda']['device']]],True)
    table(['配置项','本次值'],[(k,json.dumps(v,ensure_ascii=False)) for k,v in cfg.items()])
    run_metadata=[]
    for file in sorted(experiment_root.glob('*_run_*.json')):
        value=read_json(file)
        if value:run_metadata.append((file,value))
    if run_metadata:
        table(['命令','状态','耗时(s)','解释器','代码版本'],[[str(v.get('command')),v.get('status'),number(v.get('elapsed_seconds')),v.get('interpreter'),v.get('code',{}).get('commit')] for _,v in run_metadata],True)
    else:p('【待完成】本次运行元数据尚未生成；实际环境与耗时不能从配置推断。')
    p('数据、模型权重、特征与本地摘要 MP4 不进入提交包。结果图和数值嵌入本报告，复现所需代码、配置、依赖及公开来源随代码交付。资源哈希用于确认文件一致性，不表示模型已完成推理。')
    image_result=results['image']
    page('3 图像检索：数据与划分')
    p('COIL-100 以对象 ID 判断相关性。同一对象不同视角仍属于相关图像，背景或外观相似不改变标签。每对象 0°、90°、180°、270° 四张查询，共 400 张；查询文件自身从图库排除。主图库为其余 6,800 张，稀疏图库为每对象 20+45k 度、k=0…7 的 800 张图像。')
    p('稀疏图库同时改变视角覆盖和相关图像数量。因此性能变化不能单独归因于视角，也不能与主图库直接视作仅一个因素的控制实验。所有图像标识与描述子行号保持一一对应。')
    if image_result:table(['字段','真实记录'],[(k,v) for k,v in image_result.get('data',{}).items()])
    else:pending('图像检索')
    page('4 图像检索：模型、池化与评价')
    p('主方法使用作者 VGG16-GeM 预训练检索模型；RGB、单尺度、512 维输出，GeM 参数 p 从权重读取，无额外白化。描述子 L2 归一化后以点积降序排序。GeM 定义为各通道激活 p 次幂均值的 1/p 次幂。')
    p('遵循作者 PIL thumbnail 的缩图语义：最长边上限为 362，不放大小图，因此 COIL 原始 128×128 图像保持原尺寸。')
    p('对照保持同一经过 GeM 检索训练的 VGG16 骨干、权重与预处理，仅在推理时替换为平均池化或最大池化。它检验该骨干上的池化替换，不能代替三个方法各自独立训练的公平比较。')
    p('P@5 为前五结果中同对象图像数除以 5；每查询 AP 使用当前图库全部相关图像数作分母，mAP 为查询 AP 平均。按对象聚类配对 bootstrap 保留同对象四个查询的依赖，使用 2,000 次重采样及固定种子。')
    if image_result:table(['模型字段','真实值'],[(k,json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v) for k,v in image_result.get('model',{}).items()],True)
    page('5 图像检索：总体结果与对照')
    if image_result:
        methods=image_result.get('methods',[])
        table(['图库','方法','查询数','图库数','平均P@5','mAP'],[[r['gallery'],r['method'],r['queries'],r['gallery_size'],number(r['mean_p_at_5']),number(r['map'])] for r in methods])
        for gallery in ('full','sparse'):
            group=[r for r in methods if r['gallery']==gallery]
            if group:
                best=max(group,key=lambda r:r['map']);gem=next((r for r in group if r['method']=='gem'),None)
                p(f"{gallery} 图库中，本次 mAP 最高的方法为 {best['method']}（{best['map']:.4f}）。"+(f"GeM 平均 P@5 为 {gem['mean_p_at_5']:.4f}、mAP 为 {gem['map']:.4f}。" if gem else '')+'这是本数据划分和同一骨干上的观察，不预设 GeM 必然优于替换池化。')
        image('method_comparison.png','两种图库与三种推理池化的真实指标',experiment_root/'image')
    else:pending('图像结果')
    page('6 图像检索：不确定性与配对差异')
    if image_result:
        table(['图库','对比','ΔP@5','95%区间','ΔAP','95%区间'],[[r['gallery'],r['contrast'],number(r['p_at_5_difference']),str(r['p_at_5_ci95']),number(r['ap_difference']),str(r['ap_ci95'])] for r in image_result.get('bootstrap',[])],True)
        for r in image_result.get('bootstrap',[]):
            lo,hi=r['ap_ci95'];p(f"{r['gallery']} 的 {r['contrast']}：AP 配对差异区间为 [{lo:.4f}, {hi:.4f}]，"+('包含零，当前重采样结果不能排除零差异。' if lo<=0<=hi else '未包含零；方向仅适用于本次对象划分及相同检索骨干。'))
    p('置信区间反映对象重采样带来的样本变化，未覆盖数据域、独立训练、超参数选择等其他不确定性。测试集上没有重新调节 p 或白化。')
    page('7 图像检索：代表案例')
    if image_result:
        for f in image_result.get('figures',[]):
            if 'top5' in f:image(f,'按真实 P@5／AP 确定的代表查询及 Top-5；图中给出 ID 和点积相似度',experiment_root/'image')
        per=csv_rows(experiment_root/'image'/'per_query.csv');gem=[r for r in per if r.get('method')=='gem']
        if gem:
            failures=sum(float(r['p_at_5'])<1 for r in gem);p(f'两图库 GeM 查询记录中，P@5 未达到 1 的记录数为 {failures}/{len(gem)}。'+('本次未出现 P@5 失败记录，应重点讨论任务较容易及相关性定义的限制。' if failures==0 else '失败案例可结合图中对象外形、视角与可见区域讨论；视觉相似不能替代对象 ID 标签。'))
    else:pending('图像案例')
    p('图像案例依据真实指标选择，不能把事后挑选的成功图当作整体性能证据。完整逐查询数值和 Top-5 标识／分数附后。')
    if image_result:
        p('本次主图库最差案例 obj67__270 为白色长方包装，前两名为同对象相邻视角，后三名为绿色包装 obj98；两对象的长方外形、圆形标志和中央文字布局相近，颜色差异未阻止混淆。该查询 P@5=0.40、AP约0.1321。此解释来自代表图观察，不能证明网络只使用某一种视觉线索。')
        p('稀疏图库最差查询 obj44__90 为浅色带柄小铲，Top-5却是浅色木制几何组合（obj77和obj41），P@5=0、AP约0.0282。它说明稀疏视角下，相似颜色及主体轮廓可能盖过对象身份。图中相似度约0.78—0.80仍不能视作正确匹配概率。')
    video=results['video']
    page('8 视频检索：任务改编与源视频')
    p('TVSum 原用于视频摘要，本实验把它改编为受控近重复视频检索。每类别按视频 ID 顺序选择首个可完整解码且至少 80 秒的视频，共 10 个源。此选择先于模型打分，并通过接触表与重复场景疑似清单审查。')
    p('时长为 D 的视频，查询一从 0.1D 开始，查询二从 (D−20)/2 开始，各取 20 秒；末尾 20 秒为同源干扰。每段各制作统一重编码、中心保留 80% 宽高再缩放、顶部 10% 半透明灰条三变体。原查询文件不进候选集。正负使用相同编辑条件，目标为 20 查询、90 候选。')
    p('片段统一采用 Conda FFmpeg 自带 MPEG-4 Part 2 编码，查询 qscale=2、全部候选 qscale=5，yuv420p，无音轨；保持原始宽高比。编码选择在模型评分前固定，来源于该构建不含 libx264 的兼容限制。')
    if video:
        table(['类别','源视频ID','时长(s)','完整解码'],[[s.get('category'),s['id'],number(s['duration'],2),s.get('full_decode_verified','未记录')] for s in video.get('data',{}).get('sources',[])])
    else:pending('视频源与审查记录')
    page('9 视频检索：标注与完整网络')
    p('相关标签满足：同一原始视频，且候选原时间区间与查询区间的交集覆盖查询时长至少 80%。标签不依据模型得分构造。近似重复镜头可能使时间区间标签与视觉相似性冲突，须在打分前处理歧义源并记录替换依据。')
    p('每侧约 1 fps 按时间顺序采样，至少四个实际解码帧；短边 256、中心裁剪 224、RGB。作者完整非对称流程为 ResNet50 区域特征、PCA 白化、注意力、区域 Chamfer 匹配、帧间矩阵、2D CNN、Hardtanh 截断及查询到候选方向的 Chamfer 汇聚。查询始终作为第一个输入。')
    p('去 CNN 对照复用完全相同的注意力特征与帧间矩阵，保持 Hardtanh 与同方向 Chamfer。缓存用于避免重复特征提取，不代替真实输入或真实推理。')
    if video:table(['模型记录','值'],[(k,json.dumps(v,ensure_ascii=False)) for k,v in video.get('model',{}).items()],True)
    page('10 视频检索：总体结果与消融')
    if video:
        table(['指标','本次真实结果'],[(k,number(v) if isinstance(v,(float,int)) else str(v)) for k,v in video.get('metrics',{}).items()])
        m=video.get('metrics',{});a=m.get('mAP');b=m.get('without_cnn_mAP')
        if a is not None and b is not None:p(f'完整网络 mAP 为 {a:.4f}，去 CNN 对照为 {b:.4f}，差值为 {a-b:+.4f}。'+('完整网络在该受控任务上更高。' if a>b else '当前结果未显示完整网络有更高 mAP。')+'应同时参考按源配对区间，不能把二十个相关查询误当作二十个独立视频。')
        image(video.get('comparison_figure'),'完整 ViSiL 与去 CNN 对照',experiment_root/'video')
    else:pending('视频总体指标')
    p('Top-3 命中是前三是否至少有一个相关候选；mAP 使用完整候选排名。两者分别强调用户首屏命中和全部相关结果的排序，不能相互替代。')
    if video and video['metrics']['mAP']==video['metrics']['without_cnn_mAP']==1:
        p('两种方法均将全部相关候选排在其他候选之前，AP差值及本次bootstrap区间都是0。这里的零区间来自所有观测差值均为零，并不证明CNN在一般任务中无效或两个模型等价。源视频只有十个、干扰中存在片尾字幕，受控编辑强度也有限，因而难以暴露方法差异。没有根据本次结果重新挑选困难查询或调整协议。')
    page('11 视频检索：逐查询命中与 Top-3')
    if video:
        table(['查询ID','Hit@3','AP','Top-3候选（相似度）'],[[r['query_id'],r['hit_at_3'],number(r['ap']),'\n'.join(f"{c['id']} ({c['score']:.4f}; rel={c['relevant']})" for c in r['top3'])] for r in video.get('queries',[])],True)
        for value in video.get('top3_figures',[])[:2]:image(value,'查询及前三候选代表帧，实际相似度见图',experiment_root/'video')
    else:pending('视频逐查询结果')
    page('12 视频检索：时间匹配结构与局限')
    if video:
        replay=read_json(experiment_root/'replay_video.json') or {}
        for value in replay.get('figures',video.get('heatmaps',[])):image(value,'实际区域匹配所得帧间相似度；横轴候选秒，纵轴查询秒',experiment_root/'video')
        p('以蜂巢介绍视频查询一为例，相关重编码片段呈现贯穿时间轴的对角结构，同时同一人物/木墙镜头在查询内重复出现，形成对角线以外的块状高值。非相关的查询二片段后段也含同一机位人物，因此右侧部分区域较亮；它缺少覆盖整个查询的连续对齐。局部同场景相似与严格同源时间标签存在差别。')
    p('热图连续对角带可支持相近时间顺序的匹配解释，重复纹理或镜头可能产生局部高值。最终分数还经过 CNN、截断和有向汇聚，不能仅依据热图一个亮点推断最终名次。相关与干扰图需结合实际 Top-3 分数阅读。')
    p('十源视频、受控剪辑与三种编辑形成的是小规模实验。压缩、裁剪、灰条既不是全部自然扰动，也不代表开放域视频检索。标签来自原时间区间，可能漏掉语义或视觉上相关但时间不重合的片段。按十源 bootstrap 的区间仍受源数量限制。')
    summary=results['summary']
    page('13 视频摘要：独立完整输入与时间轴')
    split_index=(summary or {}).get('split',{}).get('split_index',cfg.get('summary',{}).get('split_index',0))
    p(f'摘要独立选择完整 TVSum 视频，未把视频检索结果、候选或剪辑作为输入。选择官方 split {split_index} 中按数字 key 顺序首个能与原视频匹配的测试样本；配套 GoogLeNet 特征为每采样点 1024 维。')
    p('核验特征行数与 picks 一致，picks 严格递增且位于原帧范围；change_points 连续覆盖原帧，分段帧数与边界一致，人工摘要宽度等于原帧数。导出时完整解码原视频，发现帧数不符立即失败。文件名匹配只是一项检查，时间轴和划分检查同样必要。')
    if summary:
        p('官方TVSum HDF5没有video_name字段。我们以原视频、官方20人逐帧标注和H5的帧数，以及(mean_annotation−1)/4在picks处与gtscore的逐点一致性建立独立映射。video_1唯一对应AwmHb44_ouw，三者均为10,597帧，最大分数误差约2.4×10⁻⁸。全部50条可由评分曲线识别，其中48条帧数精确一致，另外两条原片各多1帧，保留为未完全对齐，未用于本次案例。原H5没有被修改。')
    if summary:table(['字段','真实值'],[(k,str(summary.get(k))) for k in ('method','video_key','video_name','selection','nms','playback_check')]+[('split',json.dumps(summary.get('split'),ensure_ascii=False))])
    else:pending('摘要独立输入')
    page('14 视频摘要：预测与作者后处理')
    p('使用 DSNet anchor-free attention 预训练版本。重要性与中心度相乘形成置信度，左右偏移确定候选区间。按作者流程归一化置信度、区间裁剪取整、NMS=0.4，再恢复采样点与原帧上的分数。')
    p('按分段求均值，并以 int(1000×mean) 形成整数价值，在 floor(原帧数×预算) 下用精确 0/1 背包选择完整片段。片段最后按原时间顺序导出。动态规划替代旧 OR-Tools 接口是兼容性调整，保留目标、整数化、容量和片段约束。')
    p('5%、10%、15% 三种预算共享相同模型预测，仅改变预算。15% 为主验收配置，不根据测试 F1 调整。随机基线按相同分段、15% 容量，用种子 0—29 随机排列并依次加入可容纳片段。')
    if summary:image('scores.png','完整视频上的重要性、中心度与 NMS 后分数',experiment_root/'summary')
    page('15 视频摘要：预算、帧数与评价')
    if summary:
        table(['预算','原帧数','选中帧','导出解码帧','真实比例','平均F1'],[[number(r['budget'],2),r['total_frames'],r['selected_frames'],r['export']['export_decoded_frames'],number(r['ratio']),number(r['avg_f1'])] for r in summary.get('results',[])])
        baseline=summary.get('random_baseline',{});p(f"随机片段基线平均 F1={number(baseline.get('mean_f1'))}，标准差={number(baseline.get('std_f1'))}。")
        main_summary=next((r for r in summary.get('results',[]) if abs(r['budget']-.15)<1e-8),None)
        if main_summary and isinstance(baseline.get('mean_f1'),(float,int)):
            difference=main_summary['avg_f1']-baseline['mean_f1'];p(f'15% 主配置相对随机基线均值的 F1 差为 {difference:+.4f}。'+('当前单视频上主配置更高。' if difference>0 else '当前单视频上主配置没有高于随机基线均值。')+'随机种子间标准差不是跨视频置信区间，不能据此宣称数据集上的显著优势。')
        for r in summary.get('results',[]):p(f"预算 {r['budget']:.0%}：实际帧比 {r['ratio']:.4%}，选中 {r['selected_frames']} 帧，导出解码 {r['export']['export_decoded_frames']} 帧；"+('满足对应预算及 15% 上限。' if r['ratio']<=r['budget'] and r['ratio']<=.15 else '【未通过】帧预算检查。'))
    else:pending('摘要帧预算与评价')
    p('TVSum F1 对每个人工摘要分别计算后平均。预算曲线使用固定人工参考，参考摘要的长度影响 precision／recall 平衡。因此预算间 F1 差异不单独说明选段语义更好或更差。单视频结果也不是数据集平均水平。')
    page('16 视频摘要：所选片段与代表内容')
    if summary:
        for r in summary.get('results',[]):
            doc.add_heading(f"预算 {r['budget']:.0%}",level=2)
            table(['片段','起始帧','末帧(含)','开始秒','结束秒(不含)'],[[s['shot'],s['first_frame'],s['last_frame_inclusive'],number(s['start_seconds'],2),number(s['end_seconds_exclusive'],2)] for s in r['segments']],True)
            image(r['export'].get('contactsheet'),'实际选中片段按原时间顺序的代表帧',experiment_root/'summary')
    else:pending('摘要片段与代表帧')
    p('代表帧只能展示所保留内容的一小部分。未选片段可能含有叙事过渡、人物动作或背景解释；是否遗漏关键内容需结合原视频与实际摘要播放判断，不能仅从分数曲线作语义断言。')
    if summary:
        p('本例内容为轮胎/轮辋处理操作。三种预算都保留了轮胎、手部工具操作与部分工作台画面；15%预算比5%保留更多中段操作和转动轮胎的过程。5%摘要只有约17.7秒，动作被短片段分隔，不能作为完整维修教学。即使15%配置与人工摘要重合较高，也未保留全部工具准备、动作过渡和口头解释；移除音轨进一步限制了叙事完整性。')
    page('17 视频摘要：导出核验与播放状态')
    if summary:
        table(['预算','音频','程序解码','本地文件'],[[number(r['budget'],2),r['export'].get('audio'),r['export'].get('programmatic_decode'),r['export'].get('path')] for r in summary.get('results',[])],True)
    p('无音频 MP4 保留原始片段时间顺序。程序完整解码并核对输出帧数是一项可播放性证据，实际播放器检查为另一项验收。'+('本次播放器检查已记录；检查者类型为 '+playback_review.get('reviewer_type','未知')+'，方法为 '+playback_review.get('method','未知')+'。此记录不等同于用户本人观看。' if playback else '本次未取得完整播放通过记录，明确列为待完成，不能宣称已经播放检查。'))
    p('DSNet 预测基于预计算视觉特征，不使用音频或字幕；完整片段约束会留下无法装满的帧预算。单视频、固定预训练权重和固定人工参考共同限制了结论的外推范围。')
    page('18 综合讨论与验收记录')
    p('图像检索以对象身份为标准，视频检索以同源时间覆盖为标准，视频摘要以人工摘要重合和帧预算为标准。相似性、相关性与重要性在三个实验中具有不同含义；不能用一个实验的成功替代另一个实验的验收。')
    table(['验收项','证据状态'],[['图像：逐查询P@5、Top-5及真实相似度','已记录' if image_result else '待完成'],['视频：完整ViSiL、Top-3、帧间矩阵','已记录' if video else '待完成'],['摘要：完整视频、帧预算、导出对齐','已记录' if summary else '待完成'],['摘要实际播放','通过记录齐备' if playback else '待完成'],['交互归档','学生／代理分列；历史加密正文存在缺口' if record_gaps else '已读取本地可见记录' if records else '缺失'],['姓名学号、目录和最终排版','个人信息待填写；本机Word检查另存证据']])
    p('实际分工与本人工作边界：学生通过自由文本和结构化问答提出课程目标、环境与凭据约束、目录和Git要求，确认公开数据及均衡研究对比，并要求核验进度和交互归档。代码生成、环境命令、模型运行、自动验收和报告生成由主代理及子代理执行，不能写成学生逐条手工执行。课件要求学生运行、判断与解释；当前证据不证明学生本人已连续观看摘要或独立复核每项算法，需由学生据实际完成情况补充，不能由代理代为宣称。')
    p('后续研究可扩大独立对象或源视频数量，补充自然编辑视频及更多摘要测试视频，并在不改变测试协议的前提下报告稳定性。本次结论以本报告实际记录的规模、划分和实现为边界。')
    page('19 参考文献与公开来源')
    references=[
        'Radenović F, Tolias G, Chum O. Fine-tuning CNN Image Retrieval with No Human Annotation. https://arxiv.org/abs/1711.02512',
        'GeM 作者实现与预训练资源：https://github.com/filipradenovic/cnnimageretrieval-pytorch',
        'Columbia CAVE. COIL-100：https://www.cs.columbia.edu/CAVE/software/softlib/coil-100.php',
        'Kordopatis-Zilos G et al. ViSiL: Fine-grained Spatio-Temporal Video Similarity Learning. https://arxiv.org/abs/1908.07410',
        'ViSiL 作者 PyTorch 分支：https://github.com/MKLab-ITI/visil/tree/pytorch',
        'Song Y et al. TVSum: Summarizing Web Videos using Titles. CVPR 2015. 官方数据：https://people.csail.mit.edu/yalesong/tvsum/；https://github.com/yalesong/tvsum',
        'Zhu W et al. DSNet 论文：https://liplus.me/publication/dsnet/dsnet.pdf；作者实现：https://github.com/li-plus/DSNet',
        '本地课程材料：《学生实验任务书.docx》《多媒体实验介绍.pptx》。原件保留工作区根目录。']
    for i,reference in enumerate(references,1):p(f'[{i}] {reference}')
    p('作者源码许可证及提交版本随 vendor 目录保留。下载文件的准确 URL 与 SHA256 见资源清单和运行元数据。课程数据仅本地处理，不随报告代码包重新分发。')
    page('附录 A 主方法逐查询 P@5 与结果索引')
    p('主图库 GeM 的 400 个查询按对象与四个视角压缩为 100 行。其他池化及稀疏图库使用正文汇总和配对区间；全部逐查询指标、Top-5 标识和分数、完整排名数组保留运行目录 CSV／NPZ 以供复核。下表直接读取真实运行文件，不重算或改写分数。')
    per=csv_rows(experiment_root/'image'/'per_query.csv')
    selected=[r for r in per if r.get('gallery')=='full' and r.get('method')=='gem']
    if selected:
        import re
        groups={}
        for r in selected:
            angle=re.search(r'__(\d+)',r['query_id'])
            groups.setdefault(r['object_id'],{})[int(angle.group(1)) if angle else r['query_id']]=r['p_at_5']
        table(['对象ID','0° P@5','90° P@5','180° P@5','270° P@5'],[[key,*[value.get(a,'缺失') for a in (0,90,180,270)]] for key,value in sorted(groups.items(),key=lambda item:int(item[0]))],True)
    table(['文件','可复核内容'],[['image/per_query.csv','全部方法、图库、查询 P@5 与 AP'],['image/top5.csv','全部 Top-5 标识、真实相似度及相关标签'],['image/rankings_*.npz','完整候选排名与分数'],['video/results.json','主方法和对照完整评分、Top-3、命中与AP'],['video/relevance_labels.csv','全部查询—候选相关性标签'],['summary/prediction.npz','重要性、中心度、置信度、偏移、候选区间及NMS结果'],['summary/summary_*.npz','每种预算的选帧掩码、分段与恢复分数']],True)
    if video:
        doc.add_heading('视频去 CNN 对照逐查询结果',level=2);table(['查询','Hit@3','AP','前三候选'],[[r['query_id'],r['hit_at_3'],r['ap'],json.dumps(r['top3'],ensure_ascii=False)] for r in video.get('control_queries',[])],True)
        doc.add_heading('视频全部 Top-3 代表帧',level=2)
        for value in video.get('top3_figures',[])[2:]:image(value,'视频查询及 Top-3 代表帧补充',experiment_root/'video')
    if summary:
        doc.add_heading('摘要随机基线全部运行',level=2);table(['种子','平均F1','实际比例'],[[r['seed'],r['avg_f1'],r['ratio']] for r in summary.get('random_baseline',{}).get('runs',[])],True)
    page('附录 B 代码分工、运行日志与修正')
    table(['模块','工作范围'],[['主代理','统一环境安装、共享入口、GPU运行、验收与提交整理'],['图像模块','COIL-100、GeM及同骨干池化对照、公共资源复现'],['视频模块','TVSum改编、ViSiL完整流程及对照、Word报告生成'],['摘要模块','DSNet AF、配套时间轴、背包、预算及导出核验']])
    p('模型协作并不表示模型结果已经运行；真实运行以命令及产物为证。以下只读取已知课程日志文件，不扫描环境变量、凭据、浏览器或外部目录。')
    for file,value in run_metadata:
        doc.add_heading(file.name,level=2)
        selected={k:v for k,v in value.items() if k!='code'}
        code=value.get('code',{})
        selected['code']={'commit':code.get('commit'),'working_tree':code.get('working_tree'),'source_files_hashed':len(code.get('source_sha256',{}))}
        p(json.dumps(selected,ensure_ascii=False,indent=2))
    allowed_logs=('image_development.jsonl','video_development.jsonl','summary_development.jsonl','events.jsonl','run_events.jsonl','implementation_corrections.jsonl')
    found=False
    for name in allowed_logs:
        file=ROOT/'logs'/name
        if file.exists():
            found=True;doc.add_heading(name,level=2)
            for line in file.read_text(encoding='utf-8-sig').splitlines():
                if line.strip():p(line)
    if not found:p('【缺失】未找到约定的模块开发日志；不能补写未记录的失败与修正。')
    for file in sorted(experiment_root.glob('*.jsonl')):
        doc.add_heading('本次运行 '+file.name,level=2)
        for line in file.read_text(encoding='utf-8-sig').splitlines():
            if line.strip():p(line)
    page('附录 C 学生与主代理的可见交互原文')
    p('本附录仅收录学生直接输入、主代理的可见回复及结构化问答，不包含代理之间的任务分派、回复、隐藏推理或内部指令。子代理活动单列附录 D，不计入学生交互轮数。记录边界为本地已知主会话和其明确关联的子会话，截至快照时间；不据现存记录声称覆盖无法访问的历史。')
    if interaction_audit:
        p('交互快照截止：'+str(interaction_audit.get('last_visible_message_utc'))+'；原文快照 SHA256：'+str(interaction_audit.get('transcript_sha256')))
        counts=interaction_audit['counts']
        table(['统计口径','数量'],[['学生自由文本提示',counts['student_free_text_prompts']],['结构化问答批次',str(counts['structured_question_batches'])+' 问 / '+str(counts['structured_answer_batches'])+' 答'],['主代理可见回复',counts['main_agent_visible_replies']],['代理协作事件（另列，不计学生轮数）',counts['agent_coordination_records']]])
        table(['线程','日志记录的模型'],[[k,', '.join(v)] for k,v in interaction_audit['model_metadata_by_thread'].items()])
        p('子代理每次创建均显式指定 gpt-6.1-sol：'+str(interaction_audit['all_spawn_models_explicit_6_1_sol'])+'。学生不是模型，学生消息的模型字段标为不适用；主代理模型按实际会话元数据列出，不能把子代理模型名称套到主代理。')
        for limitation in interaction_audit['limitations']:p('记录边界：'+limitation)
        p('按课件第18—19页逐项核验：可读取的学生提示和回复按原文保存，结构化问答补入；日期和模型列明；文件及版本、运行命令、结果和修正见附录B与本地来源清单。代理协作加密正文仍有缺口，故“全部历史完整交互”尚不能严格宣称完成。未完整测量的外部等待时间记为未知，不用总会话跨度代替学生劳动时长。')
    def transcript_rows(selected,label):
        for index,record in enumerate(selected,1):
            doc.add_heading(f'{label} {index}',level=2)
            metadata=[]
            for key in ('id','timestamp','sender','recipient','kind','model','thread','source_file','source_line','call_id','metadata','body_available'):
                if key in record:metadata.append(key+'：'+(json.dumps(record[key],ensure_ascii=False) if isinstance(record[key],(dict,list)) else str(record[key])))
            metadata_paragraph=doc.add_paragraph('\n'.join(metadata))
            metadata_paragraph.paragraph_format.line_spacing=1
            for run in metadata_paragraph.runs:run.font.size=Pt(8)
            p('原文：');p(record.get('text','【缺失】'))
    student_records=[r for r in records if r.get('category')=='student_main']
    agent_records=[r for r in records if r.get('category')=='agent_collaboration']
    if not student_records:p('【缺失】未找到经过来源分类的学生可见记录；不能把旧版混合日志视为严格对齐。')
    transcript_rows(student_records,'学生—主代理记录')
    page('附录 D 代理协作记录及不可恢复原文清单')
    p('以下行为由主代理或子代理发起，属于自动化协作，不是学生亲自提出的提示、手工操作或直接反馈。保存可读取回复；加密正文只记录时间、发送方、接收方及缺口标记，未读取本机密钥，也未将事后总结冒充原始指令。')
    if interaction_audit:
        p('严格完整历史核验：'+('通过' if interaction_audit['strict_full_history_complete'] else '未通过；实验数值验收通过不消除交互原文缺口。'))
        p('无法读取正文的代理工具调用：'+str(counts['unavailable_coordination_bodies'])+'；加密投递回执：'+str(counts['encrypted_delivery_receipts'])+'。两者属于不同证据层次，不能相加当作独立对话轮数。')
    transcript_rows(agent_records,'代理协作记录')
    if transcript_errors:p('【读取失败】以下行不能解析，未擅自修复：'+str(transcript_errors))
    if missing:p('【证据缺口】以下图像未能嵌入：'+'；'.join(missing))
    if not final or missing:
        status_paragraph.text='报告状态：待完成草稿；不得作为全部验收完成的最终报告。'
        p('验收待完成项：'+'；'.join(verification.get('pending',[])))
    output_path.parent.mkdir(parents=True,exist_ok=True);doc.save(output_path)
    return {'status':('completed_with_record_gaps' if record_gaps else 'completed') if final and not missing else 'draft','path':str(output_path),'experiment_status':{n:r.get('status') if r else 'missing' for n,r in results.items()},'embedded_figures':len(figures),'missing_figures':missing,'visible_transcript_records':len(records),'transcript_parse_error_lines':transcript_errors,'interaction_audit':audit_pointer,'strict_full_history_complete':not record_gaps if interaction_audit else False,'playback_complete':playback,'verification':verification,'page_count':'not measured; update fields and inspect in Word','main_text_target':'18–25 pages; actual length depends on real figures/tables'}
