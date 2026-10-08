import json
import sys
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from meteo_pipeline.alert_map import _project
from meteo_pipeline.illustrator_map import read_illustrator_shapes
from tools.build_alert_zone_face_reference import _read_cap_snapshots

matrix=np.array(json.loads((ROOT/'output/ai_projection_matrix.json').read_text(encoding='utf8')))
zones=max(_read_cap_snapshots(ROOT/'data/raw/2026-10-01/avisos_cap.data.tar').values(),key=len)
shapes=[s for s in read_illustrator_shapes(ROOT/'MAPA_ALERTAS_ILUSTRATOR.ai') if s.layer=='ZONAS AEMET' and s.bounds[0]<1700]
scale=2
size=(960,540)
def mask(polygons):
    image=Image.new('1',size)
    dr=ImageDraw.Draw(image)
    for polygon in polygons:dr.polygon([(x/scale,y/scale) for x,y in polygon],fill=1)
    return np.asarray(image,dtype=bool)
smasks={s.form_id:mask(s.polygons) for s in shapes}
areas={f:int(m.sum()) for f,m in smasks.items()}
def project(polygon,shift=(0,0)):
    a=np.array([[*_project(lat,lon),1] for lat,lon in polygon])@matrix
    return [(float(x+shift[0]),float(y+shift[1])) for x,y in a]
def centroid(poly):
    return np.array([sum(x for x,y in poly)/len(poly),sum(y for x,y in poly)/len(poly)])
def rank(poly):
    source=mask([poly]);sa=source.sum();out=[]
    for s in shapes:
        target=smasks[s.form_id]
        intersection=np.logical_and(source,target).sum()
        if not intersection:continue
        iou=intersection/(sa+areas[s.form_id]-intersection)
        containment=intersection/max(1,min(sa,areas[s.form_id]))
        out.append((round(float(iou),3),round(float(containment),3),s.form_id))
    return sorted(out,reverse=True)[:6]
rows=[]
for code,z in sorted(zones.items()):
    if code.endswith('C') or len(z['polygons'])<2:continue
    poly0=project(z['polygons'][0]);primary=rank(poly0)
    shift=(0,0)
    if primary:
        fid=primary[0][2];s=next(s for s in shapes if s.form_id==fid)
        shift=centroid(s.polygons[0])-centroid(poly0)
    poly1=project(z['polygons'][1],shift)
    secondary=rank(poly1)
    rows.append({'code':code,'name':z['name'],'primary':primary,'shift':[round(float(v)) for v in shift], 'secondary':secondary})
    print(code,z['name'],'primary',primary[:3],'shift',tuple(round(float(v)) for v in shift),'secondary',secondary[:4])
(ROOT/'output/illustrator_split_iou_audit.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')
