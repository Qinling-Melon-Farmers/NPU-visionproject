"""DSNet AF inference and exact, frame-budgeted keyshot summaries.

Author architecture remains in vendor/dsnet (MIT). The local exact DP replaces
the obsolete ORTools binding without changing integer shot values/objective.
"""
from pathlib import Path
import json
import sys
import numpy as np

VENDOR = Path(__file__).resolve().parents[1] / 'vendor' / 'dsnet'

def save_json(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')

def knapsack(values, weights, capacity):
    """Exact 0/1 integer DP; ties prefer the earlier incumbent solution."""
    values, weights = list(values), list(weights)
    capacity = int(capacity)
    if capacity < 0 or len(values) != len(weights) or any(int(w) <= 0 for w in weights):
        raise ValueError('invalid knapsack inputs')
    dp = np.zeros(capacity + 1, dtype=np.int64)
    take = np.zeros((len(values), capacity + 1), dtype=np.bool_)
    for i, (value, weight) in enumerate(zip(values, weights)):
        weight = int(weight)
        if weight > capacity:
            continue
        candidate = dp[:-weight].copy() + int(value)
        better = candidate > dp[weight:]
        dp[weight:] = np.maximum(dp[weight:], candidate)
        take[i, weight:] = better
    chosen, remaining = [], capacity
    for i in range(len(values)-1, -1, -1):
        if take[i, remaining]:
            chosen.append(i)
            remaining -= int(weights[i])
    return sorted(chosen)

def f1_score(pred, truth):
    pred, truth = np.asarray(pred, dtype=np.bool_), np.asarray(truth, dtype=np.bool_)
    if pred.shape != truth.shape:
        raise ValueError('F1 frame axes differ')
    denominator = int(pred.sum() + truth.sum())
    return float(2 * np.logical_and(pred, truth).sum() / denominator) if denominator else 0.0

def keyshot_summary(scores, picks, cps, nfps, n_frames, budget):
    if not 0 <= budget <= .15:
        raise ValueError('frame budget must be in [0,.15]')
    frame_scores = np.zeros(n_frames, dtype=np.float32)
    for i, first in enumerate(picks):
        last = int(picks[i+1]) if i+1 < len(picks) else n_frames
        frame_scores[int(first):last] = scores[i]
    values = [int(1000 * frame_scores[int(a):int(b)+1].mean()) for a,b in cps]
    chosen = knapsack(values, nfps, int(n_frames * budget))
    mask = np.zeros(n_frames, dtype=np.bool_)
    for i in chosen:
        a,b = cps[i]
        mask[int(a):int(b)+1] = True
    assert int(mask.sum()) <= int(n_frames * budget)
    return mask, chosen, frame_scores, values

def _paths(cfg):
    root = Path(cfg['asset_root'])
    return root, root/'data/dsnet/eccv16_dataset_tvsum_google_pool5.h5', root/'weights/dsnet/pretrain_af_basic/checkpoint'/f"tvsum.yml.{cfg.get('summary',{}).get('split_index',0)}.pt"

def prepare(cfg):
    import yaml
    root, h5, checkpoint = _paths(cfg)
    split_index = cfg.get('summary',{}).get('split_index',0)
    splits = yaml.safe_load((VENDOR/'splits/tvsum.yml').read_text())
    split = splits[split_index]
    test = sorted([x.rsplit('/',1)[-1] for x in split['test_keys']], key=lambda x:int(x.split('_')[-1]))
    train = [x.rsplit('/',1)[-1] for x in split['train_keys']]
    assert not set(test) & set(train)
    return {'h5': str(h5), 'checkpoint':str(checkpoint), 'resources_ready':h5.exists() and checkpoint.exists(), 'test_keys':test, 'train_keys':train, 'split_index':split_index}

def _name(value):
    if isinstance(value, bytes):
        return value.decode('utf-8')
    return str(value)

def _export(video, mask, destination, contactsheet):
    import cv2
    import matplotlib.pyplot as plt
    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        raise RuntimeError(f'Cannot open video: {video}')
    fps = capture.get(cv2.CAP_PROP_FPS)
    width, height = int(capture.get(3)), int(capture.get(4))
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(destination)
    writer = cv2.VideoWriter(str(destination), cv2.VideoWriter_fourcc(*'mp4v'), fps, (width,height))
    if not writer.isOpened():
        raise RuntimeError('MP4 writer unavailable')
    count = written = 0
    representative = []
    targets = set(np.linspace(0, max(0,int(mask.sum())-1), 8).astype(int))
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        if count < len(mask) and mask[count]:
            writer.write(frame)
            if written in targets:
                representative.append((count, cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)))
            written += 1
        count += 1
    capture.release()
    writer.release()
    if count != len(mask):
        raise ValueError(f'Media/H5 frame mismatch: {count} != {len(mask)}')
    verify = cv2.VideoCapture(str(destination))
    decoded = 0
    while verify.read()[0]:
        decoded += 1
    verify.release()
    assert decoded == written == int(mask.sum())
    fig, axes = plt.subplots(2,4,figsize=(12,5))
    for ax in axes.flat:
        ax.axis('off')
    for ax,(index,frame) in zip(axes.flat, representative):
        ax.imshow(frame)
        ax.set_title(f'frame {index}; {index/fps:.2f}s')
    fig.tight_layout(); fig.savefig(contactsheet,dpi=150); plt.close(fig)
    return {'path':str(destination),'fps':fps,'source_decoded_frames':count,'selected_frames':written,'export_decoded_frames':decoded,'audio':False,'programmatic_decode':'passed','human_playback':'pending','contactsheet':str(contactsheet)}

def run(cfg, run_dir):
    import h5py
    import torch
    import matplotlib.pyplot as plt
    import csv
    state = prepare(cfg)
    if not state['resources_ready']:
        raise FileNotFoundError(state)
    run_dir = Path(run_dir); run_dir.mkdir(parents=True,exist_ok=True)
    sys.path.insert(0,str(VENDOR/'src'))
    from anchor_free.dsnet_af import DSNetAF
    from anchor_free.anchor_free_helper import offset2bbox
    from helpers.bbox_helper import nms
    root = Path(cfg['asset_root'])
    video_root = Path(cfg.get('summary',{}).get('video_root',root/'data/tvsum'))
    metadata_files = list(video_root.rglob('ydata-tvsum50-info.tsv'))
    if len(metadata_files) != 1:
        raise FileNotFoundError('Expected one official TVSum metadata TSV')
    with metadata_files[0].open(encoding='utf-8-sig',newline='') as stream:
        metadata = {row['video_id']:row for row in csv.DictReader(stream,delimiter='\t')}
    with h5py.File(state['h5'],'r') as h5:
        selected = None
        for key in state['test_keys']:
            group = h5[key]
            name = _name(group['video_name'][()])
            if name not in metadata:
                raise ValueError(f'H5 video_name not present in official metadata: {name}')
            matches = list(video_root.rglob(name+'.mp4'))
            if matches:
                selected = (key,name,matches[0]); break
        if selected is None:
            raise FileNotFoundError('No test video matched H5 video_name metadata')
        key,name,video = selected
        group = h5[key]
        arrays = {k:group[k][()] for k in ['features','picks','change_points','n_frame_per_seg','n_frames','user_summary']}
    features, picks, cps, nfps = (arrays[k] for k in ['features','picks','change_points','n_frame_per_seg'])
    n_frames = int(arrays['n_frames'])
    assert features.shape == (len(picks),1024)
    assert np.all(np.diff(picks)>0) and picks[0]==0 and picks[-1]<n_frames
    assert cps[0,0]==0 and cps[-1,1]==n_frames-1
    assert np.array_equal(cps[:,1]-cps[:,0]+1,nfps)
    assert np.all(cps[1:,0]==cps[:-1,1]+1)
    assert arrays['user_summary'].shape[1] == n_frames
    torch.manual_seed(cfg.get('seed',0))
    device = cfg.get('device','cpu')
    model = DSNetAF('attention',1024,128,8).to(device).eval()
    model.load_state_dict(torch.load(state['checkpoint'],map_location=device,weights_only=True))
    with torch.no_grad():
        importance,offsets,centerness = model(torch.from_numpy(features).unsqueeze(0).to(device))
    importance,offsets,centerness = [x.cpu().numpy() for x in (importance,offsets,centerness)]
    confidence = importance*centerness
    normalized = confidence/(confidence.max()+1e-8)
    boxes = np.clip(offset2bbox(offsets),0,len(features)).round().astype(np.int32)
    kept_scores, kept_boxes = nms(normalized,boxes,.4)
    scores = np.zeros(len(features),dtype=np.float32)
    for value,(a,b) in zip(kept_scores,kept_boxes):
        scores[a:b] = np.maximum(scores[a:b],value)
    np.savez_compressed(run_dir/'prediction.npz',importance=importance,centerness=centerness,confidence=confidence,normalized_confidence=normalized,offsets=offsets,boxes=boxes,nms_scores=kept_scores,nms_boxes=kept_boxes,scores=scores,**arrays)
    rows=[]
    for budget in cfg.get('summary',{}).get('budgets',[.05,.10,.15]):
        mask,chosen,frame_scores,values = keyshot_summary(scores,picks,cps,nfps,n_frames,budget)
        percent = round(100*budget)
        np.savez_compressed(run_dir/f'summary_{percent:02d}.npz',mask=mask,chosen=chosen,frame_scores=frame_scores,shot_values=values)
        export = _export(video,mask,root/'cache/summary'/run_dir.parent.name/f'{name}_{percent:02d}.mp4',run_dir/f'contactsheet_{percent:02d}.png')
        f1 = float(np.mean([f1_score(mask,user) for user in arrays['user_summary']]))
        segments=[{'shot':i,'first_frame':int(cps[i,0]),'last_frame_inclusive':int(cps[i,1]),'start_seconds':float(cps[i,0]/export['fps']),'end_seconds_exclusive':float((cps[i,1]+1)/export['fps'])} for i in chosen]
        rows.append({'budget':budget,'selected_frames':int(mask.sum()),'total_frames':n_frames,'ratio':float(mask.mean()),'avg_f1':f1,'segments':segments,'export':export})
    baseline=[]
    for seed in range(cfg.get('summary',{}).get('random_seeds',30)):
        remaining=int(n_frames*.15); mask=np.zeros(n_frames,dtype=np.bool_)
        for i in np.random.default_rng(seed).permutation(len(cps)):
            if nfps[i]<=remaining:
                a,b=cps[i]; mask[a:b+1]=True; remaining-=int(nfps[i])
        baseline.append({'seed':seed,'avg_f1':float(np.mean([f1_score(mask,u) for u in arrays['user_summary']])),'ratio':float(mask.mean())})
    result={'status':'completed','method':'DSNet anchor-free attention','video_key':key,'video_name':name,'video_path':str(video),'selection':'first numeric official split test key with matching video_name media','split':state,'nms':.4,'results':rows,'random_baseline':{'runs':baseline,'mean_f1':float(np.mean([r['avg_f1'] for r in baseline])),'std_f1':float(np.std([r['avg_f1'] for r in baseline]))},'playback_check':'programmatic decoding complete; human playback pending'}
    save_json(run_dir/'results.json',result)
    with (run_dir/'metrics.csv').open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=['budget','selected_frames','total_frames','ratio','avg_f1']); writer.writeheader(); writer.writerows([{k:r[k] for k in writer.fieldnames} for r in rows])
    fig,ax=plt.subplots(figsize=(12,4)); ax.plot(picks,importance,label='importance'); ax.plot(picks,centerness,label='centerness'); ax.plot(picks,scores,label='post-NMS score'); ax.set(xlabel='Original frame',ylabel='Score'); ax.legend(); fig.tight_layout(); fig.savefig(run_dir/'scores.png',dpi=150); plt.close(fig)
    return result
