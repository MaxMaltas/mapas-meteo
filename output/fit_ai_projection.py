import json
import sys
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from meteo_pipeline.illustrator_map import read_illustrator_shapes
from meteo_pipeline.alert_map import _project
from tools.build_alert_zone_face_reference import _read_cap_snapshots

zones=max(_read_cap_snapshots(ROOT/'data/raw/2026-10-01/avisos_cap.data.tar').values(),key=len)
shapes={s.form_id:s for s in read_illustrator_shapes(ROOT/'MAPA_ALERTAS_ILUSTRATOR.ai') if s.layer=='ZONAS AEMET' and s.bounds[0]<1700}
overlaps=json.loads((ROOT/'output/illustrator_fla_overlap.json').read_text(encoding='utf-8'))
old={x['face']:x for x in json.loads((ROOT/'config/alert_zone_faces.reference.json').read_text(encoding='utf-8'))['assignments']}
anchors=[]
for row in overlaps:
    if not row['top_faces'] or row['top_faces'][0]['iou']<.7:continue
    fid=row['form_id']; s=shapes[fid]; x=(s.bounds[0]+s.bounds[2])/2;y=(s.bounds[1]+s.bounds[3])/2
    if not (500<x<1450 and y<960):continue
    item=old[row['top_faces'][0]['face']]
    code=item['zone_code'];part=item['part']
    if code not in zones or part>=len(zones[code]['polygons']):continue
    polygon=zones[code]['polygons'][part]
    lat=sum(p[0] for p in polygon)/len(polygon);lon=sum(p[1] for p in polygon)/len(polygon)
    sx,sy=_project(lat,lon)
    anchors.append((fid,code,part,(sx,sy),(x,y)))
src=np.array([[a[3][0],a[3][1],1] for a in anchors]);dst=np.array([a[4] for a in anchors])
best=None
rng=np.random.default_rng(1)
for _ in range(3000):
    subset=rng.choice(len(anchors),size=4,replace=False)
    m=np.linalg.lstsq(src[subset],dst[subset],rcond=None)[0]
    err=np.linalg.norm(src@m-dst,axis=1)
    good=err<25
    quality=(good.sum(),-err[good].mean() if good.any() else -1e9)
    if best is None or quality>best[0]:best=(quality,good,m)
for _ in range(3):
    m=np.linalg.lstsq(src[best[1]],dst[best[1]],rcond=None)[0]
    err=np.linalg.norm(src@m-dst,axis=1)
    best=(None,err<35,m)
print('anchors',len(anchors),'inliers',int(best[1].sum()),'matrix',best[2].tolist())
(ROOT/'output/ai_projection_matrix.json').write_text(json.dumps(best[2].tolist()),encoding='utf-8')
for a,e,good in zip(anchors,err,best[1]):
    print('anchor',a[:3],round(float(e),1),'in' if good else 'OUT')
print('multipart')
for code,z in sorted(zones.items()):
    if code.endswith('C') or len(z['polygons'])<2:continue
    print(code,z['name'])
    for pi,poly in enumerate(z['polygons']):
        lat=sum(p[0] for p in poly)/len(poly);lon=sum(p[1] for p in poly)/len(poly)
        point=np.array([*_project(lat,lon),1])@best[2]
        nearby=[]
        for fid,s in shapes.items():
            x=(s.bounds[0]+s.bounds[2])/2;y=(s.bounds[1]+s.bounds[3])/2
            nearby.append((float(np.linalg.norm(point-[x,y])),fid))
        nearby.sort()
        print(' ',pi,'expected',*(round(float(v)) for v in point),'near',[(f,round(d)) for d,f in nearby[:4]])
