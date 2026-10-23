"""Arrange pre-scoring clip contacts for a documented visual label audit."""
import json
from pathlib import Path
from PIL import Image, ImageDraw

root=Path(__file__).resolve().parents[1]
manifest=json.loads((root/'manifests/video_sources.json').read_text(encoding='utf-8'))
out=root/'outputs/visual-20261023/video_review'
out.mkdir(parents=True,exist_ok=True)
rows=[]
for source in manifest['sources']:
    for kind in ('q1','q2','negative'):
        clip=next(c for c in manifest['candidates'] if c['source_id']==source['id'] and c['id'].endswith(kind+'_reencode'))
        rows.append((f"{source['category']} {source['id']} {kind}: {clip['start']:.2f}-{clip['end']:.2f}s",clip['contact_sheet']))
for offset in range(0,len(rows),6):
    sheet=Image.new('RGB',(800,1050),'white')
    draw=ImageDraw.Draw(sheet)
    for index,(title,path) in enumerate(rows[offset:offset+6]):
        draw.text((5,index*175),title,fill='black')
        with Image.open(path) as thumb:sheet.paste(thumb,(0,index*175+25))
    sheet.save(out/f'review_{offset//6}.jpg')
print(str(out))
