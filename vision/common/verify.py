"""Independent saved-evidence audit; no GPU/model inference or network requests."""
import csv
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def rows(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as stream:
        return list(csv.DictReader(stream))


def require(condition,message):
    if not condition: raise ValueError(message)


def close(actual,expected,label):
    import math
    require(math.isfinite(float(actual)) and abs(float(actual)-float(expected))<=1e-7,f'{label}: {actual} != {expected}')


def sha256(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(8*1024*1024),b''): digest.update(block)
    return digest.hexdigest()


def metrics(labels,k):
    hits=0;ap=0.
    for rank,label in enumerate(labels,1):
        if label: hits+=1;ap+=hits/rank
    return sum(labels[:k])/k,ap/hits if hits else 0.


def coil(identifier):
    match=re.fullmatch(r'obj(\d+)__(\d+)\.png',str(identifier))
    require(match is not None,f'invalid COIL ID {identifier}')
    return tuple(map(int,match.groups()))


def audit_image(cfg,root,result):
    import numpy as np
    directory=root/'image'
    expected={f'rankings_{g}_{m}.npz' for g in ('full','sparse') for m in ('gem','avg','max')}
    require({p.name for p in directory.glob('rankings_*.npz')}==expected,'exactly six ranking archives required')
    per=rows(directory/'per_query.csv');top=rows(directory/'top5.csv');summ=rows(directory/'metrics.csv')
    require((len(per),len(top),len(summ))==(2400,12000,6),'image CSV dimensions')
    pi={(r['gallery'],r['method'],r['query_id']):r for r in per}
    ti={(r['gallery'],r['method'],r['query_id'],int(r['rank'])):r for r in top}
    require(len(pi)==2400 and len(ti)==12000,'duplicate image CSV records')
    si={(r['gallery'],r['method']):r for r in summ}
    ji={(r['gallery'],r['method']):r for r in result['methods']}
    require(len(ji)==len(result['methods'])==len(si)==6,'image summary methods missing/duplicate')
    queries_expected={f'obj{o}__{a}.png' for o in range(1,101) for a in (0,90,180,270)}
    for gallery in ('full','sparse'):
        candidates_expected={f'obj{o}__{a}.png' for o in range(1,101) for a in range(0,360,5) if a not in (0,90,180,270) and (gallery=='full' or a in range(20,360,45))}
        for method in ('gem','avg','max'):
            with np.load(directory/f'rankings_{gallery}_{method}.npz',allow_pickle=False) as archive:
                queries=archive['query_ids'].astype(str).tolist();candidates=archive['candidate_ids'].astype(str).tolist();ranks=archive['rankings'];scores=archive['scores']
                require(len(queries)==len(set(queries))==400 and set(queries)==queries_expected,'query identity/uniqueness')
                require(len(candidates)==len(set(candidates))==len(candidates_expected) and set(candidates)==candidates_expected,'candidate identity/uniqueness')
                require(not set(queries)&set(candidates),'image self-match')
                require(scores.shape==ranks.shape==(400,len(candidates)) and np.isfinite(scores).all() and np.issubdtype(ranks.dtype,np.integer),'image arrays dimensions/types/finite scores')
                values=[]
                for i,query in enumerate(queries):
                    order=sorted(range(len(candidates)),key=lambda j:(-float(scores[i,j]),candidates[j]))
                    require(np.array_equal(ranks[i],order),'ranking is not exact score-sorted permutation')
                    obj,_=coil(query);labels=[coil(candidates[j])[0]==obj for j in order];p5,ap=metrics(labels,5);values.append((p5,ap))
                    record=pi[(gallery,method,query)]
                    require(int(record['object_id'])==obj,'object ID mismatch');close(record['p_at_5'],p5,'P5');close(record['ap'],ap,'AP')
                    for rank,j in enumerate(order[:5],1):
                        record=ti[(gallery,method,query,rank)]
                        require(record['candidate_id']==candidates[j] and record['relevant'].lower() in ('true','false'),'Top5 ID/label format')
                        require((record['relevant'].lower()=='true')==labels[rank-1],'Top5 relevance');close(record['score'],scores[i,j],'Top5 score')
                p5,ap=np.mean(values,axis=0)
                for record in (si[(gallery,method)],ji[(gallery,method)]):
                    require(int(record['queries'])==400 and int(record['gallery_size'])==len(candidates),'image summary scale')
                    close(record['mean_p_at_5'],p5,'mean P5');close(record['map'],ap,'mAP')
    require(result['metrics']==result['methods'],'JSON duplicate metrics differ')
    return {'image':'six archives; exact IDs, permutations, ordering, relevance and all CSV/JSON metrics verified'}


def probe(cfg,path):
    executable=Path(cfg.get('ffprobe',Path(sys.prefix)/'Library/bin/ffprobe.exe'))
    value=json.loads(subprocess.check_output([str(executable),'-v','error','-count_frames','-show_streams','-show_format','-of','json',str(path)],text=True,stderr=subprocess.PIPE))
    video=[s for s in value['streams'] if s['codec_type']=='video'];require(len(video)==1,f'exactly one video stream required: {path}')
    stream=video[0];require(str(stream.get('nb_read_frames','')).isdigit() and int(stream['nb_read_frames'])>0,f'actual nonempty frame count unavailable: {path}')
    if str(stream.get('nb_frames','')).isdigit():
        require(int(stream['nb_frames'])==int(stream['nb_read_frames']),f'container count differs from full decode: {path}')
    return value,stream


def sample_count(path,sample_fps,decoded_count=None):
    from vision.common.media import iter_frames,probe_video
    info=probe_video(path);fps=info['fps']
    if fps>144:fps=25
    step=round(fps/sample_fps);require(step>0,'invalid sample cadence')
    if decoded_count is not None:
        # Caller obtained this from ffprobe -count_frames, a full real decode.
        require(decoded_count>0,'actual decoded video is empty')
        return (decoded_count+step-1)//step,decoded_count
    count=sampled=0
    for frame in iter_frames(path):
        require(frame is not None and frame.size>0,'decoded frame unavailable')
        if count%step==0:sampled+=1
        count+=1
    return sampled,count


def relevant(q,c):
    duration=q['end']-q['start'];require(duration>0,'invalid query interval')
    overlap=max(0.,min(q['end'],c['end'])-max(q['start'],c['start']))
    return q['source_id']==c['source_id'] and overlap/duration>=.8


def audit_video(cfg,root,result):
    import numpy as np
    data=result['data'];queries=data['queries'];candidates=data['candidates'];qids=[q['id'] for q in queries];cids=[c['id'] for c in candidates]
    require(len(qids)==len(set(qids))==20 and len(cids)==len(set(cids))==90 and not set(qids)&set(cids),'video unique20x90/self-match')
    require(data.get('visual_review_approved') is True,'visual review absent');sources=data['sources'];source_ids={s['id'] for s in sources}
    require(len(sources)==len(source_ids)==10,'ten unique sources required')
    for source in sources:
        value,stream=probe(cfg,source['path']);require(float(stream.get('duration',value['format']['duration']))>=80,'source duration below80')
    counts=result['sampled_frames'];require(set(counts)==set(qids+cids),'sampling identities')
    for clip in queries+candidates:
        require(clip['source_id'] in source_ids and clip['end']>clip['start'],'clip provenance/time invalid')
        _,stream=probe(cfg,clip['path']);actual,decoded=sample_count(clip['path'],cfg.get('video',{}).get('sample_fps',1),int(stream['nb_read_frames']))
        require(actual>=4 and actual==counts[clip['id']] and decoded==int(stream['nb_read_frames']),'actual clip sampling/frame counts differ')
    labels=rows(root/'video/relevance_labels.csv');li={(r['query_id'],r['candidate_id']):int(r['relevant']) for r in labels}
    require(len(labels)==len(li)==1800,'relevance CSV dimensions')
    for score_key,row_key,prefix in [('scores','queries',''),('control_scores','control_queries','without_cnn_')]:
        scores=result[score_key];records=result[row_key];ri={r['query_id']:r for r in records}
        require(set(scores)==set(qids) and len(records)==20 and set(ri)==set(qids),'score/query identities')
        aps=[];hits=[]
        for query in queries:
            values=scores[query['id']];require(set(values)==set(cids) and np.isfinite(list(values.values())).all(),'candidate score identities/finite')
            ranked=sorted(candidates,key=lambda c:(-values[c['id']],c['id']));truth=[relevant(query,c) for c in ranked];require(any(truth),'no relevant candidate')
            for candidate,label in zip(ranked,truth):require(li[(query['id'],candidate['id'])]==int(label),'provenance relevance mismatch')
            _,ap=metrics(truth,3);hit=int(any(truth[:3]));record=ri[query['id']]
            require(record['source_id']==query['source_id'] and record['hit_at_3']==hit,'query source/hit mismatch');close(record['ap'],ap,'video AP');aps.append(ap);hits.append(hit)
            require(len(record['top3'])==3,'Top3 absent')
            for item,candidate,label in zip(record['top3'],ranked[:3],truth[:3]):
                require(item['id']==candidate['id'] and item['relevant']==label,'Top3 ranking/label mismatch');close(item['score'],values[candidate['id']],'Top3 score')
        close(result['metrics'][prefix+'mAP'],np.mean(aps),'video mAP');close(result['metrics'][prefix+'hit_at_3'],np.mean(hits),'video Hit3')
        require(result['metrics'][prefix+'successful_queries']==sum(hits),'successful query count')
    require(result['metrics']['query_count']==20 and result['metrics']['candidate_count']==90,'declared video scale')
    records=rows(root/'video/query_metrics.csv');require(len(records)==len({r['query_id'] for r in records})==20,'video CSV query dimensions');reference={r['query_id']:r for r in result['queries']}
    for record in records:
        actual=reference[record['query_id']];require(record['source_id']==actual['source_id'] and int(record['hit_at_3'])==actual['hit_at_3'],'video CSV identity/hit');close(record['ap'],actual['ap'],'video CSV AP')
    return {'video':'20x90 main/control scores, provenance labels, exact rankings/metrics, full media decode and actual sampling verified'}


def audit_summary(cfg,root,result):
    import numpy as np
    from vision.experiments.summary import keyshot_summary,f1_score
    directory=root/'summary';records=result['results'];require(len(records)==3 and sorted(round(float(r['budget']),8) for r in records)==[.05,.10,.15],'exactly three 5/10/15 percent budgets required')
    with np.load(directory/'prediction.npz',allow_pickle=False) as prediction:
        picks=prediction['picks'];cps=prediction['change_points'];nfps=prediction['n_frame_per_seg'];n=int(prediction['n_frames']);users=prediction['user_summary'];scores=prediction['scores']
        require(n>0 and users.ndim==2 and users.shape[0]>0 and users.shape[1]==n,'ground truth dimensions')
        require(len(scores)==len(picks)>0 and np.isfinite(scores).all(),'scores invalid');require(picks[0]==0 and np.all(np.diff(picks)>0) and picks[-1]<n,'picks invalid')
        require(cps.shape==(len(nfps),2) and cps[0,0]==0 and cps[-1,1]==n-1 and np.all(cps[1:,0]==cps[:-1,1]+1),'segments not continuous/complete')
        require(np.array_equal(cps[:,1]-cps[:,0]+1,nfps),'segment lengths');require(prediction['features'].shape==(len(picks),1024) and np.isfinite(prediction['features']).all(),'feature dimensions/values')
        np.testing.assert_allclose(prediction['confidence'],prediction['importance']*prediction['centerness'],rtol=1e-6,atol=1e-7)
        np.testing.assert_allclose(prediction['normalized_confidence'],prediction['confidence']/(prediction['confidence'].max()+1e-8),rtol=1e-6,atol=1e-7)
        importance=prediction['importance'];centerness=prediction['centerness'];offsets=prediction['offsets']
        require(importance.shape==centerness.shape==(len(picks),) and offsets.shape==(len(picks),2),'raw prediction dimensions')
        require(np.isfinite(offsets).all() and (offsets>0).all() and ((importance>=0)&(importance<=1)).all() and ((centerness>=0)&(centerness<=1)).all(),'raw prediction domains')
        index=np.arange(len(picks));boxes=np.stack((index-offsets[:,0],index+offsets[:,1]+1),axis=1)
        boxes=np.clip(boxes,0,len(picks)).round().astype(np.int32)
        require(np.array_equal(boxes,prediction['boxes']),'offset-derived candidate boxes differ')
        valid=boxes[:,0]<boxes[:,1];remaining_boxes=boxes[valid];remaining_scores=prediction['normalized_confidence'][valid]
        order=remaining_scores.argsort()[::-1];remaining_boxes=remaining_boxes[order];remaining_scores=remaining_scores[order];kept_boxes=[];kept_scores=[]
        while remaining_boxes.size:
            box=remaining_boxes[0];kept_boxes.append(box);kept_scores.append(remaining_scores[0])
            intersection=np.maximum(0,np.minimum(remaining_boxes[:,1],box[1])-np.maximum(remaining_boxes[:,0],box[0]))
            union=np.maximum(remaining_boxes[:,1],box[1])-np.minimum(remaining_boxes[:,0],box[0]);union=np.maximum(union,1e-6)
            keep=intersection/union<.4;remaining_boxes=remaining_boxes[keep];remaining_scores=remaining_scores[keep]
        require(np.array_equal(prediction['nms_boxes'],kept_boxes),'NMS boxes differ');np.testing.assert_allclose(prediction['nms_scores'],kept_scores,rtol=0,atol=0)
        restored=np.zeros(len(picks),dtype=np.float32)
        for score,(a,b) in zip(kept_scores,kept_boxes):restored[a:b]=np.maximum(restored[a:b],score)
        require(np.array_equal(scores,restored),'post-NMS sampled scores differ')
        import h5py
        h5_path=Path(cfg['asset_root'])/'data/dsnet/eccv16_dataset_tvsum_google_pool5.h5'
        with h5py.File(h5_path,'r') as source:
            group=source[result['video_key']]
            if 'video_name' in group:
                name=group['video_name'][()]
                if isinstance(name,bytes):name=name.decode('utf-8')
                require(str(name)==result['video_name']==Path(result['video_path']).stem,'H5 metadata/media identity mismatch')
            else:
                mapping_path=Path(__file__).resolve().parents[1]/'manifests/tvsum_h5_mapping.json'
                mapping=load(mapping_path);entry=mapping['mappings'][result['video_key']];name=result['video_name']
                require(entry['status']=='verified' and entry['video_id']==name==Path(result['video_path']).stem,'H5 independent mapping identity/status')
                require(entry['frame_count_candidates']==[name] and entry['n_frames']==n,'mapping exact unique frame-count identity')
                for path,digest in mapping['inputs'].items():require(sha256(path)==digest,'mapping input hash changed')
                evidence=[item for item in entry['candidate_evidence'] if item['video_id']==name]
                require(len(evidence)==1 and evidence[0]['score_verified'] is True,'annotation mapping evidence missing')
                require(sha256(result['video_path'])==evidence[0]['original']['sha256'],'mapping media hash changed')
                annotation=Path(cfg['asset_root'])/'data/tvsum/extracted/data/ydata-tvsum50-anno.tsv'
                user_scores=[]
                with annotation.open(encoding='utf-8',newline='') as stream:
                    for record in csv.reader(stream,delimiter='\t'):
                        if record[0]==name:user_scores.append(np.fromstring(record[2],sep=',',dtype=np.float64))
                require(len(user_scores)==20 and all(len(values)==n for values in user_scores),'official annotation users/frame axis mismatch')
                # Fixed published 1..5 rating scale, no fitted shift or scaling.
                official=(np.stack(user_scores).mean(axis=0)[picks]-1)/4
                np.testing.assert_allclose(official,group['gtscore'][()],rtol=0,atol=1e-5)
            for field in ['features','picks','change_points','n_frame_per_seg','n_frames','user_summary']:
                require(np.array_equal(prediction[field],group[field][()]),'prediction differs from official H5 '+field)
    split=result['split'];require(result['video_key'] in split['test_keys'] and result['video_key'] not in split['train_keys'],'train/test leakage')
    import yaml
    official=yaml.safe_load((Path(__file__).resolve().parents[1]/'vendor/dsnet/splits/tvsum.yml').read_text(encoding='utf-8'))[int(split['split_index'])]
    for label in ['test_keys','train_keys']:
        require(set(split[label])=={key.rsplit('/',1)[-1] for key in official[label]},'reported split differs from official '+label)
    _,source_stream=probe(cfg,result['video_path']);require(int(source_stream['nb_read_frames'])==n,'source decoded frames differ from H5')
    csv_records=rows(directory/'metrics.csv');ci={round(float(r['budget']),8):r for r in csv_records};require(len(csv_records)==len(ci)==3,'summary CSV budgets')
    media=[]
    for record in records:
        budget=float(record['budget']);percent=round(budget*100);mask,chosen,frame_scores,values=keyshot_summary(scores,picks,cps,nfps,n,budget)
        with np.load(directory/f'summary_{percent:02d}.npz',allow_pickle=False) as saved:
            require(saved['mask'].dtype==np.bool_ and np.array_equal(saved['mask'],mask),'saved mask differs from exact shot DP')
            require(np.array_equal(saved['chosen'],chosen) and np.array_equal(saved['shot_values'],values),'selected shots/values mismatch');np.testing.assert_allclose(saved['frame_scores'],frame_scores,rtol=0,atol=0)
        selected=int(mask.sum());ratio=selected/n;f1=float(np.mean([f1_score(mask,u) for u in users]))
        require(0<selected<=int(n*budget) and selected<=int(n*.15),'frame budget invalid');require(record['total_frames']==n and record['selected_frames']==selected,'selected/total counts')
        close(record['ratio'],ratio,'summary ratio');close(record['avg_f1'],f1,'avgF1')
        for key in ['selected_frames','total_frames','ratio','avg_f1']:close(ci[round(budget,8)][key],record[key],'summary CSV '+key)
        require(len(record['segments'])==len(chosen),'segment record count');export=record['export'];fps=float(export['fps']);require(fps>0,'invalid fps')
        for segment,i in zip(record['segments'],chosen):
            a,b=map(int,cps[i]);require(segment['shot']==i and segment['first_frame']==a and segment['last_frame_inclusive']==b,'segment identity/bounds');close(segment['start_seconds'],a/fps,'start time');close(segment['end_seconds_exclusive'],(b+1)/fps,'end time')
        actual,stream=probe(cfg,export['path']);require(not any(s['codec_type']=='audio' for s in actual['streams']),'audio stream present')
        require(int(stream['nb_read_frames'])==selected==export['export_decoded_frames']==export['selected_frames'],'actual exported frame count mismatch');require(export['source_decoded_frames']==n,'source export count mismatch')
        media.append({'path':str(Path(export['path']).resolve()),'sha256':sha256(export['path']),'budget':budget,'decoded_frames':selected})
    baseline=result['random_baseline'];runs=baseline['runs'];require(len(runs)==30 and {r['seed'] for r in runs}==set(range(30)),'random baseline seeds')
    for record in runs:
        mask=np.zeros(n,dtype=np.bool_);remaining=int(n*.15)
        for i in np.random.default_rng(record['seed']).permutation(len(cps)):
            if nfps[i]<=remaining:
                a,b=cps[i];mask[a:b+1]=True;remaining-=int(nfps[i])
        close(record['ratio'],mask.mean(),'random ratio');close(record['avg_f1'],np.mean([f1_score(mask,u) for u in users]),'random F1')
    close(baseline['mean_f1'],np.mean([r['avg_f1'] for r in runs]),'random mean');close(baseline['std_f1'],np.std([r['avg_f1'] for r in runs]),'random std')
    review=load(directory/'playback_review.json');require(review.get('status')=='passed' and review.get('reviewer_type') in ('agent','human') and bool(review.get('method')),'playback status/reviewer/method absent')
    reviewed=review.get('media',[]);require(len(reviewed)==3,'playback must cover three MP4s');ri={str(Path(item['path']).resolve()):item for item in reviewed}
    require(len(ri)==3 and set(ri)=={m['path'] for m in media},'playback media identity mismatch')
    for item in media:require(ri[item['path']].get('status')=='passed' and ri[item['path']].get('sha256')==item['sha256'],'playback failed or stale hash')
    return {'summary':'raw confidence, exact shot masks, budgets/F1/baselines, actual silent MP4 frame counts verified','media':media,'playback_reviewer_type':review['reviewer_type']}


def verify(cfg,experiment_root):
    """Report must require status==passed before writing completion claims.

    Every failed/missing artifact is returned in pending. Actual playback review
    schema: status=passed, reviewer_type=agent|human, method, media=[{path,
    sha256,status=passed}] for all three current exports. Agent is not human.
    """
    root=Path(experiment_root);checks=[];pending=[]
    for name,audit in [('image',audit_image),('video',audit_video),('summary',audit_summary)]:
        try:
            result=load(root/name/'results.json');require(result.get('status')=='completed','result status not completed');checks.append(audit(cfg,root,result))
        except (OSError,ValueError,KeyError,TypeError,IndexError,AssertionError,RuntimeError,ZeroDivisionError,subprocess.SubprocessError) as exc:
            pending.append(f'{name}: {type(exc).__name__}: {exc}')
    for name in ('image','video','summary'):
        try:
            replay=load(root/f'replay_{name}.json')
            require(replay.get('status')=='passed',f'{name} fresh inference replay did not pass')
        except (OSError,ValueError,KeyError,TypeError) as exc:
            pending.append(f'{name} fresh replay: {exc}')
    return {'status':'passed' if len(checks)==3 and not pending else 'incomplete','checks':checks,'pending':pending,'scope':'saved arrays and actual decoded files; model inference not repeated'}
