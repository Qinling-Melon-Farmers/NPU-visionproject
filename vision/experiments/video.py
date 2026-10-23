"""TVSum near-duplicate retrieval with the author's directional ViSiL network.

Preparation is separate from scoring so source/clip contact sheets can be reviewed
without inspecting model scores. No downloads or environment changes occur here.
"""
from pathlib import Path
import csv
import hashlib
import json
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'manifests' / 'video_sources.json'


def dump(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf-8')


def relevant(query, candidate):
    overlap = max(0., min(query['end'], candidate['end']) - max(query['start'], candidate['start']))
    return query['source_id'] == candidate['source_id'] and overlap / (query['end'] - query['start']) >= .8


def tools(cfg):
    prefix = Path(sys.executable).parent / 'Library' / 'bin'
    return str(prefix / 'ffmpeg.exe'), str(prefix / 'ffprobe.exe')


def probe(path, cfg):
    _, ffprobe = tools(cfg)
    value = json.loads(subprocess.check_output([ffprobe, '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height,nb_frames,r_frame_rate,duration:format=duration', '-of', 'json', str(path)], text=True))
    stream = value['streams'][0]
    stream['duration'] = float(stream.get('duration', value['format']['duration']))
    return stream


def prepare_sources(cfg):
    """Select by category/ID/duration before model scoring; retain all decisions."""
    root = Path(cfg['asset_root']) / 'data' / 'tvsum'
    tables = list(root.rglob('ydata-tvsum50-info.tsv'))
    if not tables:
        raise FileNotFoundError('TVSum info TSV missing; extract official archive first')
    rows = []
    with tables[0].open(encoding='utf-8') as handle:
        for row in csv.reader(handle, delimiter='\t'):
            if row and row[0] != 'category' and len(row) >= 2:
                rows.append([row[1], row[0], *row[2:]])
    selected, decisions = [], []
    for category in sorted({row[1] for row in rows}):
        for row in sorted((r for r in rows if r[1] == category), key=lambda r:r[0]):
            matches = list(root.rglob(row[0] + '.mp4'))
            if not matches:
                decisions.append({'id':row[0], 'reason':'missing'}); continue
            try:
                info = probe(matches[0], cfg)
                if info['duration'] < 80:
                    decisions.append({'id':row[0], 'reason':'duration_below_80s'}); continue
                ffmpeg, _ = tools(cfg)
                subprocess.run([ffmpeg,'-v','error','-i',str(matches[0]),'-map','0:v:0','-f','null','-'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
                selected.append({'id':row[0], 'category':category, 'path':str(matches[0]), 'full_decode_verified':True, **info})
                break
            except (subprocess.CalledProcessError, ValueError, KeyError) as exc:
                decisions.append({'id':row[0], 'reason':str(exc)})
    if len(selected) != 10:
        raise ValueError(f'Expected ten categories, selected {len(selected)}; inspect TVSum TSV')
    result = {'status':'sources_selected_pending_visual_review', 'dataset':'TVSum 1.1 adapted from summarization to near-duplicate retrieval', 'selection':'first ID per category with duration >=80 seconds and ffprobe readable', 'sources':selected, 'decisions':decisions}
    dump(MANIFEST, result)
    return result


def prepare_clips(cfg):
    from PIL import Image, ImageDraw
    import cv2
    import numpy as np
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    output = Path(cfg['asset_root']) / 'cache' / 'video' / 'clips'
    output.mkdir(parents=True, exist_ok=True)
    ffmpeg, _ = tools(cfg)
    queries, candidates, review = [], [], []
    for source in manifest['sources']:
        duration = source['duration']
        intervals = [('q1', .1 * duration), ('q2', (duration - 20) / 2), ('negative', duration - 20)]
        for kind, start in intervals:
            for variant in (['query'] if kind != 'negative' else []) + ['reencode', 'crop', 'overlay']:
                clip_id = f"{source['id']}_{kind}_{variant}"
                path = output / (clip_id + '.mp4')
                width, height = int(source['width'])//2*2, int(source['height'])//2*2
                filters = f'scale={width}:{height}'
                if variant == 'crop': filters = f'crop=trunc(iw*.8/2)*2:trunc(ih*.8/2)*2,scale={width}:{height}'
                if variant == 'overlay': filters += ',drawbox=x=0:y=0:w=iw:h=ih*.1:color=gray@0.5:t=fill'
                if not path.exists():
                    quality = '2' if variant == 'query' else '5'
                    command = [ffmpeg, '-v', 'error', '-ss', str(start), '-i', source['path'], '-t', '20', '-vf', filters, '-an', '-c:v', 'mpeg4', '-q:v', quality, '-pix_fmt', 'yuv420p', '-n', str(path)]
                    subprocess.run(command, check=True)
                item = {'id':clip_id, 'source_id':source['id'], 'category':source['category'], 'start':start, 'end':start+20, 'variant':variant, 'path':str(path), 'encoder':'mpeg4', 'qscale':2 if variant=='query' else 5, 'filters':filters}
                clip_sheet=Image.new('RGB',(800,145),'white'); clip_draw=ImageDraw.Draw(clip_sheet)
                clip_cap=cv2.VideoCapture(str(path))
                for frame_index,second in enumerate([0,4,8,12,16]):
                    clip_cap.set(cv2.CAP_PROP_POS_MSEC,second*1000);ok,frame=clip_cap.read()
                    if not ok:raise ValueError('Clip cannot decode contact frame: '+clip_id)
                    thumb=Image.fromarray(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB));thumb.thumbnail((160,120));clip_sheet.paste(thumb,(frame_index*160,0));clip_draw.text((frame_index*160,122),f'{second}s',fill='black')
                clip_cap.release(); contact=output/(clip_id+'_contact.jpg');clip_sheet.save(contact);item['contact_sheet']=str(contact)
                (queries if variant == 'query' else candidates).append(item)
        print(f"Prepared clips for {source['id']}", flush=True)
        # Source contact sheet at 1s sampling also makes repeated scenes inspectable.
        cap = cv2.VideoCapture(source['path']); thumbs = []; hashes = []
        for second in range(int(duration)):
            cap.set(cv2.CAP_PROP_POS_MSEC, second*1000); ok, frame = cap.read()
            if not ok: continue
            gray = cv2.resize(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (16,16))
            hashes.append((second, gray.astype(float)))
            if second % 5 == 0:
                thumb = Image.fromarray(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)); thumb.thumbnail((160,120)); thumbs.append((second,thumb))
        cap.release()
        sheet = Image.new('RGB',(800,145*((len(thumbs)+4)//5)), 'white'); draw=ImageDraw.Draw(sheet)
        for i,(second,thumb) in enumerate(thumbs):
            x,y=(i%5)*160,(i//5)*145; sheet.paste(thumb,(x,y)); draw.text((x,y+120),f'{second}s',fill='black')
        sheet.save(output / (source['id']+'_source_contact.jpg'))
        suspicious=[]
        for i,(a,x) in enumerate(hashes):
            for b,y in hashes[i+1:]:
                if b-a>=20:
                    error=float(np.mean(abs(x-y)))
                    if error < 5: suspicious.append({'a':a,'b':b,'gray_mae':error})
        review.append({'source_id':source['id'],'contact_sheet':str(output/(source['id']+'_source_contact.jpg')), 'suspected_repeated_frames':sorted(suspicious,key=lambda r:r['gray_mae'])[:50]})
    if len(queries)!=20 or len(candidates)!=90:
        raise ValueError(f'Unexpected retrieval size: {len(queries)} queries, {len(candidates)} candidates')
    manifest.update({'status':'clips_ready_pending_visual_review','queries':queries,'candidates':candidates,'review':review, 'relevance':'same source and intersection/query duration >= 0.8', 'visual_review_approved':False})
    dump(MANIFEST,manifest)
    return manifest


def prepare(cfg):
    return {'status':'ready' if MANIFEST.exists() else 'needs_sources', 'manifest':str(MANIFEST), 'steps':['prepare_sources(cfg)', 'prepare_clips(cfg)', 'review contact sheets and set visual_review_approved', 'run(cfg,run_dir)']}


def evaluate(scores, queries, candidates):
    rows=[]
    for query in queries:
        ranked=sorted(candidates,key=lambda c:(-scores[query['id']][c['id']],c['id']))
        labels=[relevant(query,c) for c in ranked]
        total=sum(labels)
        if total == 0: raise ValueError('No relevant candidate for '+query['id'])
        ap=sum(sum(labels[:i+1])/(i+1) for i,label in enumerate(labels) if label)/total
        rows.append({'query_id':query['id'],'source_id':query['source_id'],'hit_at_3':int(any(labels[:3])),'ap':ap,'top3':[{'id':c['id'],'score':scores[query['id']][c['id']],'relevant':relevant(query,c)} for c in ranked[:3]]})
    return rows


def run(cfg, run_dir):
    import numpy as np
    import torch
    import matplotlib.pyplot as plt
    import cv2
    from unittest.mock import patch
    run_dir=Path(run_dir);run_dir.mkdir(parents=True,exist_ok=True)
    manifest=json.loads(MANIFEST.read_text(encoding='utf-8'))
    if not manifest.get('visual_review_approved'):
        raise RuntimeError('Source/clip visual review must be approved in manifest before scoring')
    with (run_dir/'relevance_labels.csv').open('w',newline='',encoding='utf-8-sig') as handle:
        writer=csv.writer(handle);writer.writerow(['query_id','candidate_id','relevant'])
        writer.writerows((q['id'],c['id'],int(relevant(q,c))) for q in manifest['queries'] for c in manifest['candidates'])
    vendor=ROOT/'vendor'/'visil';sys.path.insert(0,str(vendor))
    from model.visil import ViSiL
    from utils import load_video
    weights=Path(cfg['asset_root'])/'weights'/'visil'
    original_load=torch.load
    def local_weight(url,*args,**kwargs):
        return original_load(weights/Path(url).name,map_location='cpu',weights_only=False)
    import torchvision.models as models
    resnet=models.resnet50
    def local_resnet(*args,**kwargs):
        kwargs.pop('pretrained',None);kwargs.pop('weights',None)
        network=resnet(*args,weights=None,**kwargs)
        network.load_state_dict(original_load(weights/'resnet50-19c8e357.pth',map_location='cpu',weights_only=True))
        return network
    with patch('torch.hub.load_state_dict_from_url',local_weight),patch('torchvision.models.resnet50',local_resnet):
        model=ViSiL(pretrained=True,symmetric=False).to(cfg['device']).eval()
    cache=Path(cfg['asset_root'])/'cache'/'video'/'features';cache.mkdir(parents=True,exist_ok=True)
    weight_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in weights.glob('*.pth')}
    feature_config={'weights':weight_hashes,'sample_fps':cfg.get('video',{}).get('sample_fps',1),'short_side':256,'center_crop':224,'attention':True,'adapter_version':2}
    config_fingerprint=hashlib.sha256(json.dumps(feature_config,sort_keys=True).encode()).hexdigest()
    features={};counts={};batch=cfg.get('video',{}).get('batch_size',8)
    with torch.inference_mode():
        for clip in manifest['queries']+manifest['candidates']:
            digest=hashlib.sha256(Path(clip['path']).read_bytes()).hexdigest()
            target=cache/(digest+'_'+config_fingerprint+'.pt')
            if target.exists():
                feature=original_load(target,map_location='cpu',weights_only=True)
            else:
                frames=load_video(clip['path'],fps=cfg.get('video',{}).get('sample_fps',1))
                if len(frames)<4: raise ValueError('Fewer than four real sampled frames: '+clip['id'])
                feature=torch.cat([model.extract_features(torch.from_numpy(frames[i:i+batch]).to(cfg['device'])).cpu() for i in range(0,len(frames),batch)])
                torch.save(feature,target)
            if feature.shape[0]<4:raise ValueError('Invalid cached frame count')
            features[clip['id']]=feature;counts[clip['id']]=int(feature.shape[0])
            print(f"video features {len(features)}/110: {clip['id']}",flush=True)
        scores={};baseline={};heatmaps=[]
        for query in manifest['queries']:
            q=features[query['id']].unsqueeze(0).to(cfg['device']);scores[query['id']]={};baseline[query['id']]={}
            picked={True:False,False:False}
            for candidate in manifest['candidates']:
                c=features[candidate['id']].unsqueeze(0).to(cfg['device'])
                matrix=model.calculate_f2f_matrix(q,c)
                score=model.visil_head.v2v_sim(model.visil_head.htanh(model.visil_head.visil_output(matrix)))
                control=model.visil_head.v2v_sim(model.visil_head.htanh(matrix))
                scores[query['id']][candidate['id']]=float(score.item());baseline[query['id']][candidate['id']]=float(control.item())
                label=relevant(query,candidate)
                if not picked[label] and len(heatmaps)<2 and (label or candidate['source_id']==query['source_id']):
                    fig,ax=plt.subplots(); ax.imshow(matrix[0].cpu().numpy(),origin='lower',aspect='auto',extent=[0,counts[candidate['id']],0,counts[query['id']]])
                    ax.set(xlabel='Candidate time (s)',ylabel='Query time (s)',title=f"{query['id']} → {candidate['id']}")
                    file=run_dir/f'frame_similarity_{len(heatmaps)}.png';fig.savefig(file,bbox_inches='tight');plt.close(fig)
                    heatmaps.append(str(file));picked[label]=True
            print(f"video ranked query {len(scores)}/20: {query['id']}",flush=True)
    main=evaluate(scores,manifest['queries'],manifest['candidates']);control=evaluate(baseline,manifest['queries'],manifest['candidates'])
    clips={c['id']:c for c in manifest['queries']+manifest['candidates']}
    top3_figures=[]
    for row in main:
        fig,axes=plt.subplots(1,4,figsize=(16,3))
        ids=[row['query_id']]+[c['id'] for c in row['top3']]
        for index,(ax,clip_id) in enumerate(zip(axes,ids)):
            cap=cv2.VideoCapture(clips[clip_id]['path']);cap.set(cv2.CAP_PROP_POS_MSEC,10000);ok,frame=cap.read();cap.release()
            if not ok:raise ValueError('Representative frame decode failed: '+clip_id)
            ax.imshow(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB));ax.axis('off')
            title='Query' if index==0 else f"#{index} score={row['top3'][index-1]['score']:.4f}"
            ax.set_title(title+'\n'+clip_id,fontsize=8)
        file=run_dir/(row['query_id']+'_top3.png');fig.savefig(file,bbox_inches='tight');plt.close(fig);top3_figures.append(str(file))
    sources=sorted({r['source_id'] for r in main});rng=np.random.default_rng(cfg.get('seed',20261023));differences=[]
    paired={s:np.mean([a['ap']-b['ap'] for a,b in zip(main,control) if a['source_id']==s]) for s in sources}
    for _ in range(2000):differences.append(float(np.mean([paired[s] for s in rng.choice(sources,len(sources),replace=True)])))
    result={'status':'completed','metrics':{'query_count':len(main),'candidate_count':len(manifest['candidates']),'successful_queries':sum(r['hit_at_3'] for r in main),'hit_at_3':float(np.mean([r['hit_at_3'] for r in main])),'mAP':float(np.mean([r['ap'] for r in main])),'without_cnn_mAP':float(np.mean([r['ap'] for r in control])),'paired_source_bootstrap_mAP_difference_ci95':np.quantile(differences,[.025,.975]).tolist()},'queries':main,'control_queries':control,'scores':scores,'control_scores':baseline,'sampled_frames':counts,'heatmaps':heatmaps,'data':manifest,'model':{'repository_commit':'5751de6d7fdd48098b35c694aa250f2f1dad6a9f','symmetric':False,'pipeline':'ResNet50 regions → PCA whitening → attention → region Chamfer → 2D CNN → Hardtanh → directional Chamfer','control':'same frame similarity, remove CNN, retain Hardtanh and directional Chamfer'}}
    result['top3_figures']=top3_figures
    result['model']['weight_sha256']=weight_hashes
    result['model']['feature_config']=feature_config
    result['metrics']['without_cnn_successful_queries']=sum(row['hit_at_3'] for row in control)
    result['metrics']['without_cnn_hit_at_3']=float(np.mean([row['hit_at_3'] for row in control]))
    result['source_manifest_sha256']=hashlib.sha256(MANIFEST.read_bytes()).hexdigest()
    fig,ax=plt.subplots(figsize=(6,4));ax.bar(['Full ViSiL','Without CNN'],[result['metrics']['mAP'],result['metrics']['without_cnn_mAP']]);ax.set(ylabel='Mean average precision',ylim=(0,1),title=f"{len(main)} queries / {len(manifest['candidates'])} candidates")
    comparison=run_dir/'comparison.png';fig.savefig(comparison,bbox_inches='tight');plt.close(fig);result['comparison_figure']=str(comparison)
    dump(run_dir/'results.json',result)
    with (run_dir/'query_metrics.csv').open('w',newline='',encoding='utf-8-sig') as handle:
        writer=csv.DictWriter(handle,fieldnames=['query_id','source_id','hit_at_3','ap']);writer.writeheader();writer.writerows({k:r[k] for k in writer.fieldnames} for r in main)
    return result
