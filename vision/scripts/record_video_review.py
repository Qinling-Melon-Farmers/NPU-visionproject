"""Record the 2026-10-23 agent audit performed before any ViSiL scores."""
import json
from datetime import datetime, timezone
from pathlib import Path
from vision.common.io import sha256

root=Path(__file__).resolve().parents[1]
manifest_path=root/'manifests/video_sources.json'
manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
if manifest.get('visual_review_approved'):raise RuntimeError('Review already recorded; do not overwrite')
notes={
    'EE-bNr36nyA':'蜂巢插图和固定机位人物镜头在不同时段出现；查询一含蜂巢/远景，查询二含人物近景/木墙，末段含蜂巢/淡出片尾。重复局部没有覆盖任一20秒查询的80%，保留并在局限讨论局部重复。',
    'EYqVtI9YWJA':'访谈与摩托车动作交替；末段为黑衣骑手和片尾，疑似重复为首尾黑帧，未覆盖查询。',
    '-esJrBWj2d8':'查询一为儿童与喂猫准备，查询二为猫进食近景，末段为盘子和猫离开，未见重复播放。',
    'JKpqYvAdIsw':'连续街头舞蹈多机位剪辑；查询分属开场与红裙舞者段，末段为观众/群舞收尾，未见查询80%重放。',
    '0tmA_C6XwfM':'主持人场景与片头片尾标志重复；查询一含主持人及抱狗，查询二为剪爪特写，末段为主持人/玩具/标志，未见完整查询重复。',
    '37rzWOQsNIw':'查询一三明治展示，查询二喂鸽子，末段其他食物/人物/字幕，未见重复播放。',
    'GsAD1KT1xo8':'城市跑酷与旅行蒙太奇；多个地点相同但动作与镜头序列不同，末段跳跃/栏杆收尾，未见重复序列。',
    '4wU_LUjG5Ic':'骑车游行与不同受访者；末段人群与赞助字幕，疑似重复为首尾黑帧，未覆盖查询。',
    '98MoyGZKHXc':'轮胎维修连续步骤；查询一片头/车轮/车内，查询二压缩机/车轮操作，末段车内人物与订阅页，未见80%查询重复。',
    'HT5vyqe0Xaw':'同一路段卡车救援连续记录；查询一走近卡车，查询二前侧视角，末段卡车离开后的道路，存在同场景相似但未见重复剪辑。',
}
assert set(notes)=={s['id'] for s in manifest['sources']}
for clip in manifest['queries']+manifest['candidates']:
    clip['sha256']=sha256(clip['path'])
for source in manifest['sources']:
    source['sha256']=sha256(source['path'])
review={'status':'passed','reviewer_type':'agent','timestamp':datetime.now(timezone.utc).isoformat(),
        'performed_before_model_scoring':True,
        'method':'主代理逐一查看10张全片每5秒接触表、5张查询/同源干扰汇总图（30段，每段5帧）及1fps灰度重复候选清单。按80%覆盖标准检查重复镜头歧义；此为抽帧视觉审查，不声称逐帧人工观看。',
        'sources':notes,'replacements':[],
        'limitations':'稀疏抽帧不能排除所有局部相似；部分片尾字幕使干扰更易区分，十源受控结论不外推。'}
manifest['visual_review_approved']=True
manifest['visual_review']=review
manifest['status']='clips_reviewed_ready_for_scoring'
archive=root/'outputs/visual-20261023/video_review/approved_manifest.json'
if archive.exists():raise FileExistsError(archive)
archive.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print('10 sources / 20 queries / 90 candidates reviewed before model scoring')
