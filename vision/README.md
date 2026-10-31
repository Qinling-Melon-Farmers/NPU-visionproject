# 视觉实验复现说明

本目录实现 GeM 图像检索、完整 ViSiL 视频检索与 DSNet 无锚框视频摘要。正式结果为 `outputs/visual-20261023-fp32`，三个模型已真实加载权重并完成严格 FP32 推理、固定查询重放和文件验收，20 项测试通过（含交互来源分类）。首轮 `visual-20261023` 保留作修正证据。根目录原始任务书和课件保留只读。语音实验不在本目录范围内。

## 提交包

视觉部分单独提交包为 `submission/2023302610_肖怀瑾_vision.zip`，结构如下：

```text
README.md             本说明（提交包根目录另附运行要点）
report/               vision_report.docx 与 vision_report.pdf
vision/               课程代码、作者代码（vendor/）、配置、清单、测试和运行脚本
```

包内不含数据集、预训练权重、特征缓存和运行日志；数据与模型路径由
[configs/default.yaml](configs/default.yaml) 的 `asset_root` 指定。

## 环境与配置

从工作区根目录运行下列 PowerShell 命令。只使用专用 Conda 环境，课程 Python 命令均带 `-s`；不得改用系统 Python、base、`pip --user` 或修理其他课程环境。默认配置为 [configs/default.yaml](configs/default.yaml)：

```yaml
asset_root: E:/MultimediaCourseAssets/vision
environment_prefix: E:/MultimediaCourseAssets/envs/multimedia-vision
device: cuda
```

更换存储位置时，复制配置文件并修改这两个路径，后续命令用 `--config <新配置>`。CLI 核验当前 `sys.prefix` 与 `environment_prefix` 完全匹配，同时要求禁用用户级包。数据、下载档、权重、特征及视频缓存保存在 `asset_root`；代码中不需要修改盘符。

环境定义见 [environment.yml](environment.yml)。下例通过单次命令限定官方源，不修改 Conda 全局配置；先解算检查，再移除 `--dry-run` 执行实际创建。不要对已经存在的环境盲目重跑创建或批量改核心依赖。

```powershell
$courseEnv = 'E:\MultimediaCourseAssets\envs\multimedia-vision'
$env:CONDA_PKGS_DIRS = 'E:\MultimediaCourseAssets\conda-pkgs'
$env:CONDA_REPORT_ERRORS = 'false'
conda create -p $courseEnv --override-channels -c https://conda.anaconda.org/pytorch -c https://conda.anaconda.org/nvidia -c https://repo.anaconda.com/pkgs/main python=3.11 pytorch=2.5.1 torchvision=0.20.1 pytorch-cuda=11.8 numpy=1.26.4 opencv=4.10 h5py scipy matplotlib pillow pyyaml python-docx ffmpeg pytest tqdm --dry-run
# 核对解算结果后，用同一命令去掉 --dry-run 创建环境。
conda run -p $courseEnv python -s -c "import sys; print(sys.executable); print(sys.flags.no_user_site)"
conda run -p $courseEnv python -s vision/scripts/environment_check.py
conda list -p $courseEnv --explicit
conda env export -p $courseEnv --no-builds
```

`environment_check.py` 会实际检查包来源、CUDA 11.8、GPU 小矩阵运算、NumPy 桥接及环境内 FFmpeg/ffprobe。GPU 不可用时检查会失败，不能据安装成功推断可运行。本机专用环境已经通过检查，证据见 `manifests/environment_validation.json`；PyTorch 使用官方 GPU 构建，实际安装包和来源由 `conda-explicit-win-64.txt` 及 `environment-lock-win-64.yml` 固定。不要导出完整环境变量或带认证信息的源地址。

## 公开资源与准备

作者代码随 `vendor/` 保留，版本和许可证见 [vendor/README.md](vendor/README.md)。公开 URL、实际 SHA256 在 `manifests/image_sources.json`、`summary_sources.json`、`video_resources.json`；`video_sources.json` 是后续生成的视频划分与审查清单，两者用途不同。

空资源目录可顺序重建全部公开资源：

```powershell
conda run --no-capture-output -p $courseEnv python -s -m vision prepare --download --config vision/configs/default.yaml --run-id prepare-01
# 或仅调用资源准备，不运行实验：
.\vision\scripts\prepare_resources.ps1 -AssetRoot 'E:\MultimediaCourseAssets\vision' -EnvironmentPath $courseEnv
```

资源准备只发匿名公开 HTTP(S) 请求，不读取浏览器、Cookie、令牌或本机登录信息。已存在资源先核验 SHA256，匹配则复用；不匹配时保留原文件并报错。断点续传校验 URL 和服务器版本标识；服务器忽略 Range 时使用新的临时文件，失败记录与部分文件保留。归档解压拒绝路径逃逸和链接。网络失败后可重试同一资源命令；不得通过删除已有资源绕过校验。

预期资源布局如下（归档及解压层级按清单生成）：

```text
asset_root/
  downloads/coil-100.zip, tvsum50_ver_1_1.tgz, dsnet_datasets.zip, dsnet_pretrain_af_basic.zip
  data/coil-100/coil-100/obj1__0.png ...
  data/tvsum/extracted/data/*.tsv
  data/tvsum/extracted/video/*.mp4
  data/dsnet/eccv16_dataset_tvsum_google_pool5.h5
  weights/gem/retrievalSfM120k-vgg16-gem-b4dcdc6.pth
  weights/visil/visil.pth, pca_resnet50_vcdb_1M.pth, resnet50-19c8e357.pth
  weights/dsnet/pretrain_af_basic/checkpoint/tvsum.yml.0.pt
  cache/                         按输入、权重和预处理指纹隔离
  resource_verification/         每次资源校验清单
```

GeM 使用作者检索权重的参数 `p`、RGB、单尺度512维、无额外白化。作者使用 PIL thumbnail：362为最长边上限，COIL 的128×128图片保持原大小；三个池化方法使用完全相同的预处理。400查询为每对象0/90/180/270度，主图库6800图，稀疏图库为20+45k度共800图，查询与图库不重叠。

DSNet 使用官方 TVSum GoogLeNet1024维 H5 和对应 AF checkpoint，默认官方 split0；资源脚本仅提取需要的 H5 和配置对应的 checkpoint。摘要从完整原视频独立运行，不读取检索排名。预算为5%、10%、15%，帧预算、原帧映射及导出帧数均须依据真实输出验收。

官方DSNet H5的`video_name`仅适用于SumMe，TVSum不能猜测编号顺序。可独立运行映射核验：

```powershell
conda run -p $courseEnv python -s vision/scripts/build_tvsum_mapping.py --asset-root 'E:\MultimediaCourseAssets\vision'
```

`manifests/tvsum_h5_mapping.json`保存H5、官方TSV及原视频哈希、帧数、评分曲线比较和50项映射证据。固定按官方1–5分范围归一化`(20人平均分-1)/4`，在H5 picks处全表最大误差约`2.3842e-8`；50项评分曲线均唯一识别，48项原视频/标注/H5帧数严格一致。`video_16 → WG0MBPpPC6I`为原视频9535帧、标注/H5 9534帧，`video_39 → Se3oxnaPsz0`为原视频4166帧、标注/H5 4165帧；两项实际解码确认差1帧，清单保留未通过严格时间轴核验状态，没有静默截断。当前摘要使用完全核验的`video_1 → AwmHb44_ouw`（10597帧），映射依据不涉及模型预测或F1选样。

## 视频划分及视觉审查

默认`prepare --video-stage status`只返回视频准备状态，不自动完成选源、切片或视觉审查。环境就绪后显式调用：

```powershell
conda run --no-capture-output -p $courseEnv python -s -m vision prepare --target video --video-stage sources --run-id prepare-sources-01
conda run --no-capture-output -p $courseEnv python -s -m vision prepare --target video --video-stage clips --run-id prepare-clips-01
```

选源按类别、视频 ID、可完整解码且至少80秒的规则生成10个源；20秒查询及同源干扰片段产生20查询、90候选，统一包含重编码、裁剪和遮挡条件。TVSum 原用于摘要，本实验将其改编为受控近重复检索；相关性定义为同源且原时间交集覆盖查询至少80%。

本机官方Conda OpenCV4.10构建缺少FFmpeg Video I/O，`common/media.py`使用当前专用环境`Library/bin`的FFmpeg/ffprobe替代视频解码，OpenCV只执行图像resize。RGB管道以`-vsync 0`逐帧输出、不复制帧；采样在单个FFmpeg进程内选择作者定义的帧序号`0, round(source_fps/request_fps), ...`，随后执行相同INTER_CUBIC短边256和中心224裁剪。此替代避免GStreamer/MSMF打开失败与延迟，没有改变ViSiL采样或图像预处理定义。

必须在正式打分前查看 `video_sources.json` 的 `review`、源视频接触图、片段接触图及疑似重复帧，并按需播放原片段，检查重复镜头造成的标签歧义。存在歧义时先修订选源和清单、重新生成切片，保留理由；不可根据模型排名挑选数据。核验无误后在清单记录审查者、日期、查看对象和结论，再将 `visual_review_approved` 设为 `true`。这是实际视觉检查证据门禁，不能只为让运行通过而置位。重新调用 `prepare_sources/prepare_clips` 会重新写清单并将审查标志重置，修改前先保存已有清单版本。未通过审查的 `video` 命令会停止。

## 正式运行、验证与报告

所有命令从工作区根目录运行；三实验独立启动，避免旧作者代码包名相互污染。

```powershell
conda run --no-capture-output -p $courseEnv python -s -m vision image --run-id visual-run-01
conda run --no-capture-output -p $courseEnv python -s -m vision video --run-id visual-run-01
conda run --no-capture-output -p $courseEnv python -s -m vision summary --run-id visual-run-01
conda run -p $courseEnv python -s -m pytest vision/tests
conda run -p $courseEnv python -s vision/scripts/replay_image.py --config vision/configs/default.yaml --run-root vision/outputs/visual-run-01
conda run -p $courseEnv python -s vision/scripts/replay_models.py --kind video --config vision/configs/default.yaml --run-root vision/outputs/visual-run-01
conda run -p $courseEnv python -s vision/scripts/replay_models.py --kind summary --config vision/configs/default.yaml --run-root vision/outputs/visual-run-01
conda run -p $courseEnv python -s -m vision.scripts.check_summary_playback --run-root vision/outputs/visual-run-01
conda run -p $courseEnv python -s -m vision verify --run-id visual-run-01
conda run -p $courseEnv python -s -m vision report --run-id visual-run-01
```

默认配置以外的配置须在每条命令追加同一 `--config`。CLI 日志保存于 `vision/logs/`，元数据、配置、代码指纹、错误及结果保存在 `vision/outputs/<run-id>/`。三个实验目录一旦包含证据便拒绝重跑；失败后用新的 run-id，保留失败目录和日志，不能清空或覆盖。缓存可复用；算法或预处理改变后必须重新运行受影响实验。

图像输出包括逐查询P@5/AP、Top-5 CSV、完整排名压缩档、两图库三方法对比、对象配对bootstrap和案例图。视频输出包含完整ViSiL与去CNN对照、Top-3、逐查询命中/AP、真实帧间矩阵及代表帧。摘要输出包含候选区间、各预算选帧、帧数验收和本地无音频MP4。实际播放摘要后保存有依据的播放审查记录；程序解码不等于人工播放。`verify` 会指出尚缺的记录，不能将待完成项描述为已验收。

图像可另外对固定4查询执行独立重放：

```powershell
conda run -p $courseEnv python -s vision/scripts/replay_image.py --config vision/configs/default.yaml --run-root vision/outputs/<新的运行编号>
```

重放从原图和真实权重新计算查询特征，图库复用原指纹缓存；对主/稀疏图库和三池化方法检查保存NPZ的Top-5标识完全一致及所有候选分数最大误差不超过`1e-6`。输出`replay_image.json`拒绝覆盖，失败也保留实际差异，不自动放宽阈值。此命令会执行模型前向，应按GPU统一调度安排。

正式运行显式关闭 CUDA/cuDNN 的 TF32，设置最高 FP32 矩阵精度、确定性卷积并关闭 benchmark。首轮发现改变批次后分数最大差 `4.798e-5`，因此统一重跑三个模型并更新缓存指纹；最终图像重放最大差 `4.1723e-7`，24 组 Top-5 完全一致。视频前两查询重新提取特征后两方法 Top-3 和分数均通过，摘要三个网络输出逐元素一致。`verify` 要求三份独立重放记录均通过。

摘要播放脚本使用 FFplay 软件渲染器离屏、正常时钟播放完整三段，记录每一帧及退出码，并逐帧比较源片选帧与导出视频。当前记录属于代理工具检查，另检查代表帧，没有声称由人类连续观看。重新运行会拒绝覆盖已有播放证据。

Word 报告生成于 `vision/reports/`，真实结果图表直接嵌入，缺少结果、交互记录或播放证据时为草稿。交互附录只来自已保存的用户可见提示、回复和执行证据；不可补造无法访问的历史对话、模型版本或隐藏推理。提交前在 Word 中更新目录、填写姓名学号并检查图片、分页及参考文献。

交互记录已专项审计。学生与编程大模型的记录位于附录 C，代理协作位于附录 D，后者不计入学生交互轮数。旧版混合日志保留，新报告根据 `logs/interaction_audit_latest.json` 读取分类快照。两批结构化问答已经补回；62 次代理协作的历史正文仅有加密持久化记录，无法读取，故“全部历史交互严格完整”未通过。报告封面、附录明确此边界，不把实验验证通过等同于历史记录无缺口。

最终提交一份涵盖三个实验及完整可见交互附录的 `.docx`，并附同版 PDF；另附代码、配置、来源清单、许可证、必要运行说明及依赖信息。提交包内保留 `vision` 的课程代码、测试、说明、配置、作者来源/许可证及所需结果证据与最终报告；不把资源根目录、Conda环境、数据、权重、特征缓存或本地摘要MP4放入包内，也不为打包删除这些本地资源。摘要MP4只留本地检查。

当前报告为 [reports/delivery-20261028/vision_report.docx](reports/delivery-20261028/vision_report.docx)（另附同目录 PDF），由 [reports/build_report_v2.py](reports/build_report_v2.py) 生成。Word 16 更新目录后为正文 30 页（第 1—30 页）、全篇 82 页；32 图、28 表；附录 C 从第 44 页开始，附录 D 从第 72 页开始。姓名学号已按同机课程报告填写；封面已删除实验地点和指导教师两行。交互历史缺口不会因排版和打包而消除。
