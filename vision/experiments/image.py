"""COIL-100 retrieval: author VGG16-GeM and controlled pooling ablations."""
from pathlib import Path
import csv
import hashlib
import json
import re
import time

ROOT = Path(__file__).resolve().parents[1]
WEIGHT = 'retrievalSfM120k-vgg16-gem-b4dcdc6.pth'

def _json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')

def _hash(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''): h.update(block)
    return h.hexdigest()

def split_manifest(paths):
    rows = []
    for path in paths:
        m = re.fullmatch(r'obj(\d+)__(\d+)\.png', Path(path).name)
        if m:
            obj, angle = map(int, m.groups())
            rows.append(dict(id=Path(path).name, object_id=obj, angle=angle, path=str(path),
                             query=angle in (0,90,180,270), sparse=angle in range(20,360,45)))
    return sorted(rows, key=lambda r: r['id'])

def rank_candidates(query_id, candidate_ids, scores):
    return sorted((i for i in range(len(scores)) if candidate_ids[i] != query_id),
                  key=lambda i: (-float(scores[i]), candidate_ids[i]))

def retrieval_metrics(relevance, total_relevant=None):
    total = sum(relevance) if total_relevant is None else total_relevant
    hits = 0
    ap = 0.0
    for rank, relevant in enumerate(relevance, 1):
        if relevant:
            hits += 1
            ap += hits / rank
    return {'p_at_5': sum(relevance[:5]) / 5, 'ap': ap / total if total else 0.0}

def prepare(cfg):
    root = Path(cfg['asset_root'])
    paths = list((root/'data'/'coil-100').rglob('obj*__*.png'))
    rows = split_manifest(paths)
    if len(rows) != 7200 or len({r['id'] for r in rows}) != 7200:
        raise RuntimeError(f'COIL-100 requires 7200 unique images; found {len(rows)}')
    if {(r['object_id'],r['angle']) for r in rows} != {(o,a) for o in range(1,101) for a in range(0,360,5)}:
        raise RuntimeError('Unexpected COIL object/angle coverage')
    weight = root/'weights'/'gem'/WEIGHT
    if not weight.is_file(): raise FileNotFoundError(weight)
    return dict(status='prepared', images=rows, image_count=len(rows), queries=400,
                galleries={'full':6800,'sparse':800}, weight=str(weight), weight_sha256=_hash(weight))

def _descriptors(cfg, prepared):
    import numpy as np
    import torch
    import torchvision
    from vision.common.runtime import configure_fp32
    numerics=configure_fp32()
    from torchvision import transforms
    from PIL import Image
    import sys
    sys.path.insert(0, str(ROOT/'vendor'/'cirtorch'))
    from cirtorch.layers.functional import gem, l2n
    state = torch.load(prepared['weight'], map_location='cpu', weights_only=False)
    meta = state['meta']
    if meta['architecture'] != 'vgg16' or meta['pooling'] != 'gem' or any(meta.get(k,False) for k in ('whitening','local_whitening','regional')):
        raise RuntimeError('Checkpoint configuration differs from required VGG16-GeM')
    # Author features remove the final max-pool; instantiate without downloading ImageNet weights.
    features = torchvision.models.vgg16(weights=None).features[:-1]
    features.load_state_dict({k[len('features.'):]:v for k,v in state['state_dict'].items() if k.startswith('features.')}, strict=True)
    p = state['state_dict']['pool.p'].clone()
    size = int(cfg.get('image',{}).get('image_size',362))
    fingerprint = hashlib.sha256(json.dumps(dict(weight=prepared['weight_sha256'],size=size,
        mean=meta['mean'],std=meta['std'],rgb=True,resize='PIL thumbnail lanczos',
        inputs=[(r['id'],_hash(r['path'])) for r in prepared['images']],adapter=2,numerics=numerics),sort_keys=True).encode()).hexdigest()
    cache = Path(cfg['asset_root'])/'cache'/'image'/f'{fingerprint}.npz'
    if cache.exists():
        with np.load(cache) as data: return {k:data[k] for k in ('gem','avg','max')}, float(p.item()), fingerprint
    device = cfg.get('device','cuda')
    features.to(device).eval()
    p = p.to(device)
    transform = transforms.Compose([transforms.ToTensor(),transforms.Normalize(meta['mean'],meta['std'])])
    output = {k:[] for k in ('gem','avg','max')}
    batch_size = int(cfg.get('image',{}).get('batch_size',16))
    with torch.inference_mode():
        for start in range(0,len(prepared['images']),batch_size):
            tensors=[]
            for row in prepared['images'][start:start+batch_size]:
                with Image.open(row['path']) as src:
                    im=src.convert('RGB'); im.thumbnail((size,size),Image.Resampling.LANCZOS)
                    tensors.append(transform(im))
            x=features(torch.stack(tensors).to(device))
            pooled={'gem':gem(x,p=p),'avg':x.mean((-2,-1),keepdim=True),'max':x.amax((-2,-1),keepdim=True)}
            for name,value in pooled.items(): output[name].append(l2n(value).flatten(1).cpu().numpy())
            print(f'image descriptors {min(start+batch_size,len(prepared["images"]))}/{len(prepared["images"])}',flush=True)
    output={k:np.concatenate(v) for k,v in output.items()}
    if any(v.shape != (7200,512) or not np.isfinite(v).all() for v in output.values()): raise RuntimeError('Invalid descriptors')
    cache.parent.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(cache,**output)
    return output,float(p.item()),fingerprint

def run(cfg, run_dir):
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from PIL import Image
    run_dir=Path(run_dir); run_dir.mkdir(parents=True,exist_ok=True)
    started=time.time(); prepared=prepare(cfg)
    descriptors,p,fingerprint=_descriptors(cfg,prepared)
    rows=prepared['images']; qi=[i for i,r in enumerate(rows) if r['query']]
    metric_rows=[]; top_rows=[]; summaries=[]; values={}; examples={}
    for gallery in ('full','sparse'):
        gi=[i for i,r in enumerate(rows) if not r['query'] and (gallery=='full' or r['sparse'])]
        ids=[rows[i]['id'] for i in gi]
        for method,vectors in descriptors.items():
            scores=vectors[qi]@vectors[gi].T; rankings=[]; vals=[]
            for qpos,q in enumerate(qi):
                order=rank_candidates(rows[q]['id'],ids,scores[qpos]); rankings.append(order)
                relevant=[rows[gi[j]]['object_id']==rows[q]['object_id'] for j in order]
                metrics=retrieval_metrics(relevant); vals.append([metrics['p_at_5'],metrics['ap']])
                metric_rows.append(dict(gallery=gallery,method=method,query_id=rows[q]['id'],object_id=rows[q]['object_id'],**metrics))
                for rank,j in enumerate(order[:5],1): top_rows.append(dict(gallery=gallery,method=method,query_id=rows[q]['id'],rank=rank,candidate_id=ids[j],score=float(scores[qpos,j]),relevant=relevant[rank-1]))
                if method=='gem': examples[(gallery,qpos)]=(q,[gi[j] for j in order[:5]],[float(scores[qpos,j]) for j in order[:5]])
            values[(gallery,method)]=np.array(vals)
            np.savez_compressed(run_dir/f'rankings_{gallery}_{method}.npz',query_ids=np.array([rows[i]['id'] for i in qi]),candidate_ids=np.array(ids),rankings=np.array(rankings),scores=scores)
            summaries.append(dict(gallery=gallery,method=method,queries=len(qi),gallery_size=len(gi),mean_p_at_5=float(np.mean(vals,axis=0)[0]),map=float(np.mean(vals,axis=0)[1])))
    for name,records in [('per_query.csv',metric_rows),('top5.csv',top_rows),('metrics.csv',summaries)]:
        with (run_dir/name).open('w',newline='',encoding='utf-8-sig') as f:
            writer=csv.DictWriter(f,fieldnames=list(records[0])); writer.writeheader(); writer.writerows(records)
    rng=np.random.default_rng(20261023); bootstrap=[]
    objects=np.array([rows[i]['object_id'] for i in qi]); object_ids=np.unique(objects)
    for gallery in ('full','sparse'):
        for other in ('avg','max'):
            differences=values[(gallery,'gem')]-values[(gallery,other)]
            by_object=np.array([differences[objects==o].mean(0) for o in object_ids])
            samples=by_object[rng.integers(0,100,(2000,100))].mean(1)
            bootstrap.append(dict(gallery=gallery,contrast=f'gem-{other}',unit='object',replicates=2000,seed=20261023,
                p_at_5_difference=float(differences[:,0].mean()),p_at_5_ci95=np.quantile(samples[:,0],[.025,.975]).tolist(),
                ap_difference=float(differences[:,1].mean()),ap_ci95=np.quantile(samples[:,1],[.025,.975]).tolist()))
    figures=[]
    for gallery in ('full','sparse'):
        vals=values[(gallery,'gem')]
        for label,pos in [('best',int(np.lexsort((np.arange(len(qi)),-vals[:,1],-vals[:,0]))[0])),('worst',int(np.lexsort((np.arange(len(qi)),vals[:,1],vals[:,0]))[0]))]:
            q,top,similarities=examples[(gallery,pos)]; fig,axes=plt.subplots(1,6,figsize=(15,3))
            for n,i in enumerate([q]+top):
                with Image.open(rows[i]['path']) as im: axes[n].imshow(im.copy())
                axes[n].axis('off'); axes[n].set_title(rows[i]['id']+(' query' if n==0 else f'\n{similarities[n-1]:.4f}'),fontsize=8)
            fig.suptitle(f'{gallery} {label}: P@5={vals[pos,0]:.2f}, AP={vals[pos,1]:.4f}')
            fig.tight_layout(); filename=f'{gallery}_{label}_top5.png'; fig.savefig(run_dir/filename,dpi=150);plt.close(fig);figures.append(filename)
    fig,axes=plt.subplots(1,2,figsize=(10,4))
    for ax,key,title in zip(axes,('mean_p_at_5','map'),('Mean P@5','mAP')):
        for offset,gallery in enumerate(('full','sparse')):
            ax.bar(np.arange(3)+offset*.35,[next(s[key] for s in summaries if s['gallery']==gallery and s['method']==m) for m in ('gem','avg','max')],width=.35,label=gallery)
        ax.set_xticks(np.arange(3)+.175,['GeM','Average','Max']);ax.set_ylim(0,1);ax.set_title(title);ax.legend()
    fig.tight_layout();fig.savefig(run_dir/'method_comparison.png',dpi=160);plt.close(fig);figures.append('method_comparison.png')
    result=dict(status='completed',methods=summaries,metrics=summaries,bootstrap=bootstrap,figures=figures,
        data=dict(name='COIL-100',source='https://www.cs.columbia.edu/CAVE/software/softlib/coil-100.php',images=7200,queries=400,relevance='same object ID',query_angles=[0,90,180,270],sparse_angles=list(range(20,360,45))),
        model=dict(name=WEIGHT,source='https://cmp.felk.cvut.cz/cnnimageretrieval/data/networks/retrieval-SfM-120k/'+WEIGHT,author_code='https://github.com/filipradenovic/cnnimageretrieval-pytorch',author_commit='1e66a417afa2247edde6d35f3a9a2a465778a3a8',sha256=prepared['weight_sha256'],p=p,dimension=512,single_scale=True,whitening=False,preprocessing=f'RGB; PIL thumbnail LANCZOS longest side limit {cfg.get("image",{}).get("image_size",362)} (no upsampling); checkpoint mean/std; L2 normalization',ablations='same GeM retrieval-trained backbone, pooling replaced only',cache_fingerprint=fingerprint),elapsed_seconds=time.time()-started)
    _json(run_dir/'results.json',result);return result
