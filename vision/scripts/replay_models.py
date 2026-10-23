"""Replay one model family per fresh process against saved real-run evidence.

Invocation: python -s vision/scripts/replay_models.py --kind video|summary
 --config vision/configs/default.yaml --run-root vision/outputs/RUN
Device is taken from the config. This script never installs or downloads files.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import traceback

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT.parent) not in sys.path:sys.path.insert(0,str(ROOT.parent))
TOLERANCE=1e-5

def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def digest(path):
    result=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(8*1024*1024),b''):result.update(block)
    return result.hexdigest()

def require(value,message):
    if not value:raise ValueError(message)

def summary_replay(cfg,run_root):
    import h5py
    import numpy as np
    import torch
    from vision.common.runtime import configure_fp32
    numerics=configure_fp32()
    result=load(run_root/'summary/results.json');require(result['status']=='completed','summary not completed')
    h5=Path(cfg['asset_root'])/'data/dsnet/eccv16_dataset_tvsum_google_pool5.h5'
    split_index=int(result['split']['split_index'])
    require(split_index==int(cfg.get('summary',{}).get('split_index',0)),'summary split config differs')
    checkpoint=Path(cfg['asset_root'])/'weights/dsnet/pretrain_af_basic/checkpoint'/f'tvsum.yml.{split_index}.pt'
    sys.path.insert(0,str(ROOT/'vendor/dsnet/src'))
    from anchor_free.dsnet_af import DSNetAF
    torch.manual_seed(cfg.get('seed',0));device=cfg.get('device','cpu')
    model=DSNetAF('attention',1024,128,8).to(device).eval()
    model.load_state_dict(torch.load(checkpoint,map_location=device,weights_only=True))
    with h5py.File(h5,'r') as source:features=source[result['video_key']]['features'][()]
    with torch.inference_mode():
        outputs=model(torch.from_numpy(features).unsqueeze(0).to(device))
    errors={}
    with np.load(run_root/'summary/prediction.npz',allow_pickle=False) as saved:
        require(np.array_equal(features,saved['features']),'H5 feature input changed')
        for key,value in zip(('importance','offsets','centerness'),outputs):
            actual=value.cpu().numpy();reference=saved[key]
            require(actual.shape==reference.shape and np.isfinite(actual).all(),f'{key} output shape/finite check')
            error=float(np.max(np.abs(actual-reference)));errors[key]={'max_abs_error':error,'shape':list(actual.shape),'passed':error<=TOLERANCE}
    passed=all(item['passed'] for item in errors.values())
    return {'status':'passed' if passed else 'failed','device':device,'numerics':numerics,'video_key':result['video_key'],'arrays':errors,
            'inputs':{'h5_sha256':digest(h5),'checkpoint_sha256':digest(checkpoint),'prediction_sha256':digest(run_root/'summary/prediction.npz')}}

def video_replay(cfg,run_root):
    import numpy as np
    import torch
    from vision.common.runtime import configure_fp32
    numerics=configure_fp32()
    import torchvision.models as models
    from unittest.mock import patch
    from vision.common.media import sample_frames,probe_video
    result=load(run_root/'video/results.json');require(result['status']=='completed','video not completed')
    data=result['data'];queries=data['queries'][:2];candidates=data['candidates']
    require(len(queries)==2 and len(candidates)==90,'expected first two queries and all90 candidates')
    weights=Path(cfg['asset_root'])/'weights/visil'
    weight_hashes={p.name:digest(p) for p in weights.glob('*.pth')}
    feature_config={'weights':weight_hashes,'sample_fps':cfg.get('video',{}).get('sample_fps',1),'short_side':256,'center_crop':224,'attention':True,'decoder':'FFmpeg raw RGB; author frame-index stride','adapter_version':4,'numerics':numerics}
    require(weight_hashes==result['model']['weight_sha256'],'model weights changed')
    require(feature_config==result['model']['feature_config'],'preprocessing/weight configuration differs')
    fingerprint=hashlib.sha256(json.dumps(feature_config,sort_keys=True).encode()).hexdigest()
    cache=Path(cfg['asset_root'])/'cache/video/features';device=cfg.get('device','cpu')
    torch.manual_seed(cfg.get('seed',0));original_load=torch.load;original_resnet=models.resnet50
    sys.path.insert(0,str(ROOT/'vendor/visil'))
    from model.visil import ViSiL
    def local_weight(url,*args,**kwargs):
        return original_load(weights/Path(url).name,map_location='cpu',weights_only=False)
    def local_resnet(*args,**kwargs):
        kwargs.pop('pretrained',None);kwargs.pop('weights',None)
        model=original_resnet(*args,weights=None,**kwargs)
        model.load_state_dict(original_load(weights/'resnet50-19c8e357.pth',map_location='cpu',weights_only=True));return model
    with patch('torch.hub.load_state_dict_from_url',local_weight),patch('torchvision.models.resnet50',local_resnet):
        model=ViSiL(pretrained=True,symmetric=False).to(device).eval()
    features={};cache_evidence=[]
    for candidate in candidates:
        media_hash=digest(candidate['path']);path=cache/(media_hash+'_'+fingerprint+'.pt')
        require(path.is_file(),f'provenance-keyed feature cache missing: {candidate["id"]}')
        feature=original_load(path,map_location='cpu',weights_only=True)
        require(isinstance(feature,torch.Tensor) and feature.shape[0]==result['sampled_frames'][candidate['id']] and feature.shape[0]>=4 and torch.isfinite(feature).all().item(),'candidate cached feature invalid')
        features[candidate['id']]=feature
        cache_evidence.append({'candidate_id':candidate['id'],'media_sha256':media_hash,'feature_sha256':digest(path),'cache_key':path.name})
    records=[];batch=int(cfg.get('video',{}).get('batch_size',8));matrices={};matrix_candidates={}
    first=queries[0]
    def is_relevant(candidate):
        overlap=max(0.,min(first['end'],candidate['end'])-max(first['start'],candidate['start']))
        return first['source_id']==candidate['source_id'] and overlap/(first['end']-first['start'])>=.8
    for label,truth in [('relevant',True),('distractor',False)]:
        matches=[c for c in candidates if c['source_id']==first['source_id'] and c['variant']=='reencode' and is_relevant(c)==truth]
        require(bool(matches),'missing same-source '+label+' reencode candidate')
        matrix_candidates[label]=matches[0]
    with torch.inference_mode():
        for query in queries:
            frames=sample_frames(query['path'],fps=feature_config['sample_fps'])
            require(len(frames)==result['sampled_frames'][query['id']] and len(frames)>=4,'replayed query sample count differs')
            query_features=torch.cat([model.extract_features(torch.from_numpy(frames[i:i+batch]).to(device)).cpu() for i in range(0,len(frames),batch)])
            q=query_features.unsqueeze(0).to(device);scores={};controls={}
            for candidate in candidates:
                matrix=model.calculate_f2f_matrix(q,features[candidate['id']].unsqueeze(0).to(device))
                if query['id']==first['id']:
                    for label,item in matrix_candidates.items():
                        if candidate['id']==item['id']:matrices[label]=matrix[0].cpu().numpy()
                scores[candidate['id']]=float(model.visil_head.v2v_sim(model.visil_head.htanh(model.visil_head.visil_output(matrix))).item())
                controls[candidate['id']]=float(model.visil_head.v2v_sim(model.visil_head.htanh(matrix)).item())
            comparisons={}
            for name,actual,key in [('full',scores,'scores'),('without_cnn',controls,'control_scores')]:
                reference=result[key][query['id']]
                require(set(actual)==set(reference),'candidate score identities changed')
                errors={cid:abs(actual[cid]-reference[cid]) for cid in actual}
                require(all(np.isfinite(list(actual.values()))),'nonfinite replay scores')
                order=sorted(actual,key=lambda cid:(-actual[cid],cid))
                expected=sorted(reference,key=lambda cid:(-reference[cid],cid))
                maximum=max(errors.values());identical=order[:3]==expected[:3]
                comparisons[name]={'passed':maximum<=TOLERANCE and identical,'max_abs_error':maximum,'top3_identical':identical,'top3':order[:3],'reference_top3':expected[:3],'scores':actual,'absolute_errors':errors}
            records.append({'query_id':query['id'],'media_sha256':digest(query['path']),'fresh_sampled_frames':len(frames),'fresh_feature_shape':list(query_features.shape),'comparisons':comparisons})
            print('replayed video query '+query['id'],flush=True)
    passed=all(comparison['passed'] for record in records for comparison in record['comparisons'].values())
    require(set(matrices)=={'relevant','distractor'},'both requested frame matrices required')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    vmin=min(float(m.min()) for m in matrices.values());vmax=max(float(m.max()) for m in matrices.values())
    if vmax==vmin:vmax=vmin+1e-8
    figures=[];archive={};matrix_metadata={}
    q_info=probe_video(first['path']);qstep=round((25 if q_info['fps']>144 else q_info['fps'])/feature_config['sample_fps'])/q_info['fps']
    for label,matrix in matrices.items():
        candidate=matrix_candidates[label];info=probe_video(candidate['path'])
        cstep=round((25 if info['fps']>144 else info['fps'])/feature_config['sample_fps'])/info['fps']
        qtimes=np.arange(matrix.shape[0])*qstep;ctimes=np.arange(matrix.shape[1])*cstep
        archive[label+'_matrix']=matrix;archive[label+'_query_seconds']=qtimes;archive[label+'_candidate_seconds']=ctimes
        archive[label+'_query_id']=np.array(first['id']);archive[label+'_candidate_id']=np.array(candidate['id'])
        fig,ax=plt.subplots(figsize=(7,5))
        heatmap=ax.imshow(matrix,origin='lower',aspect='auto',extent=[-.5*cstep,ctimes[-1]+.5*cstep,-.5*qstep,qtimes[-1]+.5*qstep],vmin=vmin,vmax=vmax,cmap='viridis')
        ax.set(xlabel='Candidate time (s)',ylabel='Query time (s)',title=f"{label}: {first['id']} → {candidate['id']}")
        fig.colorbar(heatmap,ax=ax,label='Frame-to-frame similarity (before video CNN)')
        fig.tight_layout();path=run_root/f'replay_similarity_{label}.png';fig.savefig(path,dpi=160);plt.close(fig);figures.append(str(path))
        matrix_metadata[label]={'query_id':first['id'],'candidate_id':candidate['id'],'shape':list(matrix.shape),'candidate_relevant':is_relevant(candidate),'vmin':vmin,'vmax':vmax}
    matrix_archive=run_root/'replay_video_matrices.npz';np.savez_compressed(matrix_archive,**archive)
    return {'status':'passed' if passed else 'failed','device':device,'query_selection':'first two saved manifest queries, freshly sampled and feature-extracted','candidate_count':90,'feature_config':feature_config,'cache_fingerprint':fingerprint,'candidate_cache_evidence':cache_evidence,'queries':records,'input_results_sha256':digest(run_root/'video/results.json'),'figures':figures,'matrix_archive':str(matrix_archive),'matrix_archive_sha256':digest(matrix_archive),'matrix_metadata':matrix_metadata}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kind',choices=['video','summary'],required=True)
    parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--run-root',type=Path,required=True)
    args=parser.parse_args();destination=args.run_root/f'replay_{args.kind}.json'
    if destination.exists():raise FileExistsError(destination)
    if args.kind=='video':
        for filename in ['replay_video_matrices.npz','replay_similarity_relevant.png','replay_similarity_distractor.png']:
            if (args.run_root/filename).exists():raise FileExistsError(args.run_root/filename)
    import yaml
    cfg=yaml.safe_load(args.config.read_text(encoding='utf-8-sig'))
    require(Path(sys.prefix).resolve()==Path(cfg['environment_prefix']).resolve() and sys.flags.no_user_site,'Use configured dedicated Conda environment and python -s')
    os.environ['TORCH_HOME']=str(Path(cfg['asset_root'])/'cache/torch')
    value={'kind':args.kind,'timestamp_utc':datetime.now(timezone.utc).isoformat(),'tolerance':TOLERANCE,'interpreter':sys.executable,'process_id':os.getpid(),'config_sha256':digest(args.config),'script_sha256':digest(__file__)}
    try:
        value.update((video_replay if args.kind=='video' else summary_replay)(cfg,args.run_root))
    except Exception as exc:
        value.update(status='failed',error_type=type(exc).__name__,error=str(exc),traceback=traceback.format_exc())
    with destination.open('x',encoding='utf-8') as stream:json.dump(value,stream,ensure_ascii=False,indent=2)
    print(json.dumps({'status':value['status'],'path':str(destination)},ensure_ascii=False))
    return 0 if value['status']=='passed' else 1

if __name__=='__main__':raise SystemExit(main())
