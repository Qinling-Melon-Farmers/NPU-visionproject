"""Identify DSNet TVSum H5 entries by independent frame count and human scores.

No feature inference, summary prediction, F1-based selection or H5 writes occur.
"""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import subprocess
import sys
import h5py
import numpy as np

WORKSPACE=Path(__file__).resolve().parents[2]
if str(WORKSPACE) not in sys.path:sys.path.insert(0,str(WORKSPACE))
from vision.common.media import probe_video, _tool

def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as source:
        for chunk in iter(lambda:source.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def minmax(values):
    span=values.max()-values.min()
    return (values-values.min())/span if span else np.zeros_like(values)

def build(asset_root,output):
    root=Path(asset_root);data=root/'data/tvsum/extracted/data'
    annotation=data/'ydata-tvsum50-anno.tsv';info=data/'ydata-tvsum50-info.tsv'
    h5path=root/'data/dsnet/eccv16_dataset_tvsum_google_pool5.h5'
    metadata={row['video_id']:row for row in csv.DictReader(info.open(encoding='utf-8'),delimiter='\t')}
    labels={}
    with annotation.open(encoding='utf-8') as stream:
        for row in csv.reader(stream,delimiter='\t'):
            labels.setdefault(row[0],[]).append(np.fromstring(row[2],sep=',',dtype=np.float64))
    originals={}
    for path in sorted((root/'data/tvsum/extracted/video').glob('*.mp4')):
        video=path.stem;measure=probe_video(path)
        means=np.stack(labels[video]).mean(0)
        originals[video]={'path':str(path),'sha256':digest(path),'probe':measure,'annotation_users':len(labels[video]),
            'annotation_frames':len(means),'category':metadata[video]['category'],'title':metadata[video]['title'],'mean':means}
    inputs={str(p):digest(p) for p in (h5path,annotation,info)}
    mappings={};failures=[]
    with h5py.File(h5path,'r') as source:
        for key in sorted(source,key=lambda k:int(k.split('_')[-1])):
            group=source[key];n=int(group['n_frames'][()]);picks=np.asarray(group['picks'],dtype=np.int64);target=np.asarray(group['gtscore'],dtype=np.float64)
            candidates=[video for video,item in originals.items() if item['probe']['frame_count']==n and item['annotation_frames']==n]
            diagnostic_candidates=[video for video,item in originals.items() if item['probe']['frame_count']==n or item['annotation_frames']==n]
            evidence=[]
            for video in diagnostic_candidates:
                original=originals[video];full=original['mean'];sampled=full[picks]
                if original['probe']['frame_count']!=n and 'decoded_frame_count' not in original:
                    counted=subprocess.run([_tool('ffprobe'),'-v','error','-count_frames','-select_streams','v:0',
                        '-show_entries','stream=nb_read_frames','-of','json',original['path']],capture_output=True,check=True)
                    original['decoded_frame_count']=int(json.loads(counted.stdout)['streams'][0]['nb_read_frames'])
                transforms={'raw_mean':sampled,'divide_by_5':sampled/5,'fixed_rating_1_to_5':(sampled-1)/4,'minmax_full_then_picks':minmax(full)[picks],
                    'picks_then_minmax':minmax(sampled)}
                comparisons={name:{'max_abs_error':float(np.max(np.abs(values-target))),
                    'rmse':float(np.sqrt(np.mean((values-target)**2))),
                    'correlation':float(np.corrcoef(values,target)[0,1]) if np.std(values)>0 and np.std(target)>0 else None}
                    for name,values in transforms.items()}
                best=min(comparisons,key=lambda name:comparisons[name]['max_abs_error'])
                evidence.append({'video_id':video,'original':{k:v for k,v in original.items() if k!='mean'},
                    'transforms':comparisons,'best_transform':best,'score_verified':comparisons[best]['max_abs_error']<=1e-5,
                    'original_minus_h5_frames':original['probe']['frame_count']-n,'annotation_minus_h5_frames':original['annotation_frames']-n,
                    'score_samples':[{'pick':int(picks[j]),'official_mean':float(sampled[j]),'h5_gtscore':float(target[j]),
                        'normalized_official':float(transforms[best][j])} for j in range(min(12,len(picks)))]})
            passed=[item for item in evidence if item['score_verified']]
            unique=len(candidates)==1 and len(passed)==1
            result={'status':'verified' if unique else 'unresolved','n_frames':n,'n_steps':len(picks),
                'picks_min':int(picks.min()),'picks_max':int(picks.max()),'frame_count_candidates':candidates,'candidate_evidence':evidence}
            if unique:result['video_id']=passed[0]['video_id'];result['video_path']=passed[0]['original']['path']
            else:
                failures.append(key)
                if len(passed)==1:
                    result['score_identified_candidate']=passed[0]['video_id']
                    result['limitation']='Annotation curve identifies candidate but exact decoded-container frame count check failed; do not silently treat timelines as identical.'
            mappings[key]=result
            print(key,result['status'],result.get('video_id'),flush=True)
            # Persist each completed check so video_1 is independently reviewable immediately.
            manifest={'status':'verified' if len(mappings)==50 and not failures else 'partial_or_unresolved',
                'method':'unique exact original/annotation/H5 frame count AND fixed conventional annotation normalization error <=1e-5',
                'threshold_note':'1e-5 numerical tolerance; no per-video fitting, offset shifts or F1 selection. Initial raw,/5,and observed-range minmax checks gave correlation~1 but failed error. Added the fixed 1-to-5 rating-scale transform (mean-1)/4 uniformly for all 50, retaining all transform comparisons.',
                'inputs':inputs,
                'mappings':mappings,'unresolved_keys':failures,'verified_count':sum(r['status']=='verified' for r in mappings.values()),
                'score_identified_count':sum(r.get('video_id',r.get('score_identified_candidate')) is not None for r in mappings.values()),
                'all_originals':{video:{k:v for k,v in item.items() if k!='mean'} for video,item in originals.items()},
                'provenance':'Official DSNet archive readme says video_name optional and available only for SumMe; TVSum annotation TSV supplies per-frame user scores. Original video hashes and measured frame counts included per mapping.'}
            Path(output).parent.mkdir(parents=True,exist_ok=True)
            Path(output).write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    return manifest

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--asset-root',required=True)
    parser.add_argument('--output',default=str(WORKSPACE/'vision/manifests/tvsum_h5_mapping.json'))
    args=parser.parse_args();result=build(args.asset_root,args.output)
    print('verified',result['verified_count'],'unresolved',result['unresolved_keys'])
