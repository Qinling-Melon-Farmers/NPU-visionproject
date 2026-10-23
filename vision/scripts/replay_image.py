"""Independent fresh-query replay against the saved gallery/ranking evidence."""
from pathlib import Path
import argparse
import hashlib
import json
import sys
import time

WORKSPACE=Path(__file__).resolve().parents[2]
if str(WORKSPACE) not in sys.path:sys.path.insert(0,str(WORKSPACE))
QUERIES=('obj1__0.png','obj25__90.png','obj50__180.png','obj100__270.png')

def replay(config,run_root):
    import yaml
    cfg=yaml.safe_load(Path(config).read_text(encoding='utf-8'))
    if Path(sys.prefix).resolve()!=Path(cfg['environment_prefix']).resolve() or not sys.flags.no_user_site:
        raise RuntimeError('Use configured dedicated Conda prefix with python -s')
    import numpy as np
    import torch
    import torchvision
    from vision.common.runtime import configure_fp32
    numerics=configure_fp32()
    from torchvision import transforms
    from PIL import Image
    from vision.experiments.image import prepare,rank_candidates,_hash,ROOT
    run_root=Path(run_root);image_root=run_root/'image';output=run_root/'replay_image.json'
    if output.exists():raise FileExistsError(f'Replay evidence already exists: {output}')
    result=json.loads((image_root/'results.json').read_text(encoding='utf-8'))
    prepared=prepare(cfg)
    if prepared['weight_sha256']!=result['model']['sha256']:raise ValueError('Original/replay weight SHA256 differs')
    state=torch.load(prepared['weight'],map_location='cpu',weights_only=False);meta=state['meta']
    if meta['architecture']!='vgg16' or meta['pooling']!='gem':raise ValueError('Required checkpoint architecture mismatch')
    sys.path.insert(0,str(ROOT/'vendor/cirtorch'))
    from cirtorch.layers.functional import gem,l2n
    features=torchvision.models.vgg16(weights=None).features[:-1]
    features.load_state_dict({k[len('features.'):]:v for k,v in state['state_dict'].items() if k.startswith('features.')},strict=True)
    device=cfg.get('device','cuda');features.to(device).eval();p=state['state_dict']['pool.p'].to(device)
    size=int(cfg.get('image',{}).get('image_size',362));rows=prepared['images'];index={row['id']:i for i,row in enumerate(rows)}
    fingerprint=hashlib.sha256(json.dumps(dict(weight=prepared['weight_sha256'],size=size,mean=meta['mean'],std=meta['std'],
        rgb=True,resize='PIL thumbnail lanczos',inputs=[(r['id'],_hash(r['path'])) for r in rows],adapter=2,numerics=numerics),sort_keys=True).encode()).hexdigest()
    if fingerprint!=result['model']['cache_fingerprint']:raise ValueError('Current input/preprocessing fingerprint differs from original run')
    transform=transforms.Compose([transforms.ToTensor(),transforms.Normalize(meta['mean'],meta['std'])])
    tensors=[]
    for query in QUERIES:
        with Image.open(rows[index[query]]['path']) as source:
            image=source.convert('RGB');image.thumbnail((size,size),Image.Resampling.LANCZOS);tensors.append(transform(image))
    started=time.monotonic()
    with torch.inference_mode():
        x=features(torch.stack(tensors).to(device))
        fresh={name:l2n(value).flatten(1).cpu().numpy() for name,value in
            {'gem':gem(x,p=p),'avg':x.mean((-2,-1),keepdim=True),'max':x.amax((-2,-1),keepdim=True)}.items()}
    cache=Path(cfg['asset_root'])/'cache/image'/f'{fingerprint}.npz';checks=[]
    with np.load(cache) as stored_gallery:
        for gallery in ('full','sparse'):
            gi=[i for i,r in enumerate(rows) if not r['query'] and (gallery=='full' or r['sparse'])]
            ids=[rows[i]['id'] for i in gi]
            for method in ('gem','avg','max'):
                # Only gallery rows enter replay; query rows in the shared archive are never used.
                gallery_vectors=stored_gallery[method][gi]
                scores=fresh[method]@gallery_vectors.T
                with np.load(image_root/f'rankings_{gallery}_{method}.npz') as saved:
                    if saved['candidate_ids'].tolist()!=ids:raise ValueError('Saved candidate ID/order differs')
                    saved_queries=saved['query_ids'].tolist()
                    for position,query in enumerate(QUERIES):
                        q=saved_queries.index(query);order=rank_candidates(query,ids,scores[position])
                        previous=saved['rankings'][q,:5].tolist()
                        maximum=float(np.max(np.abs(scores[position]-saved['scores'][q])))
                        exact=order[:5]==previous
                        checks.append({'query_id':query,'gallery':gallery,'method':method,
                            'top5_ids':[ids[i] for i in order[:5]],'saved_top5_ids':[ids[i] for i in previous],
                            'top5_exact':exact,'max_abs_score_difference_all_candidates':maximum,
                            'score_tolerance':1e-6,'score_passed':maximum<=1e-6,
                            'recomputed_top5_scores':[float(scores[position,i]) for i in order[:5]],
                            'saved_top5_scores':[float(saved['scores'][q,i]) for i in previous]})
    passed=all(r['top5_exact'] and r['score_passed'] for r in checks)
    evidence={'status':'passed' if passed else 'failed','queries':list(QUERIES),'checks':checks,
        'query_source':'fresh original RGB images and real checkpoint forward; no cached query descriptors used',
        'gallery_source':'original descriptor cache gallery rows only','cache_fingerprint':fingerprint,'cache_sha256':_hash(cache),
        'weight_sha256':prepared['weight_sha256'],'config_sha256':_hash(config),'device':str(device),'interpreter':sys.executable,
        'max_abs_score_difference':max(r['max_abs_score_difference_all_candidates'] for r in checks),
        'numerics':numerics,'tolerance_relaxed':False,'elapsed_seconds':time.monotonic()-started}
    with output.open('x',encoding='utf-8') as stream:json.dump(evidence,stream,ensure_ascii=False,indent=2)
    return evidence

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--config',required=True);parser.add_argument('--run-root',required=True)
    args=parser.parse_args();result=replay(args.config,args.run_root)
    print(json.dumps({'status':result['status'],'checks':len(result['checks']),'max_abs_score_difference':result['max_abs_score_difference']},indent=2))
    raise SystemExit(0 if result['status']=='passed' else 1)
