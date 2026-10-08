import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from collections import Counter
from PIL import Image, ImageDraw
import numpy as np
from tools.build_alert_zone_face_reference import _read_cap_snapshots, _minimum_cost_assignment
from meteo_pipeline.alert_map import _planar_faces, read_alert_shape, _polygon_centroid

snap = _read_cap_snapshots(Path('data/raw/2026-10-01/avisos_cap.data.tar'))
allzones = max(snap.values(), key=len)
parts = [(c, k, poly) for c,z in sorted(allzones.items()) if not c.endswith('C') for k,poly in enumerate(z['polygons']) if not (c=='694304' and k==1)]
faces = _planar_faces(read_alert_shape(Path('data/alert_map_template/DOMDocument.xml'),'Capa_4'))
main_parts=[(c,k,p) for c,k,p in parts if not c.startswith(('64','65','78','79'))]
main_faces=[i for i,f in enumerate(faces) if i not in list(range(22,30))+list(range(181,196))+[198,199]]
assert len(main_parts)==len(main_faces)==175
matrix=np.array([[90.62040288074171,7.127272113678237],[3.8106931378317377,-117.54813366969704],[1087.9473551853685,5222.066708413059]])
scale=4
def render(points):
    im=Image.new('1',(480,270));d=ImageDraw.Draw(im)
    d.polygon([(round(x/scale),round(y/scale)) for x,y in points],fill=1)
    return np.asarray(im, dtype=bool)
def srcpoints(poly):
    return [tuple(np.array([lon,lat,1])@matrix) for lat,lon in poly]
sources=[render(srcpoints(p)) for c,k,p in main_parts]
targets=[render(faces[i]) for i in main_faces]
src_a=np.array([m.sum() for m in sources]); tgt_a=np.array([m.sum() for m in targets]);
scores=np.empty((175,175))
for i in range(175):
    for j in range(175):
        intersection=np.logical_and(sources[i],targets[j]).sum()
        union=src_a[i]+tgt_a[j]-intersection
        scores[i,j] = intersection/union if union else 0
costs=1-scores
assigned=_minimum_cost_assignment(costs.tolist())
rows=[]
for i,j in enumerate(assigned):
    c,k,p=main_parts[i]
    rows.append({'code':c,'name':allzones[c]['name'],'part':k,'face':main_faces[j],'iou':round(float(scores[i,j]),3),'top':[{'face':main_faces[jj],'iou':round(float(scores[i,jj]),3)} for jj in np.argsort(scores[i])[-3:][::-1]]})
print('main iou mean',np.mean([r['iou'] for r in rows]),'min',min(r['iou'] for r in rows),'below.1',sum(r['iou']<.1 for r in rows),'below.2',sum(r['iou']<.2 for r in rows))
for row in sorted(rows,key=lambda r:r['iou'])[:25]:print('worst',row)
old={ (x['code'],x['part']):x['face'] for x in json.loads(Path('output/geometry_probe_mapping.json').read_text())}
print('changed',sum(old[(r['code'],r['part'])]!=r['face'] for r in rows))
best_for_face=np.argmax(scores,axis=0)
best_scores=scores[best_for_face,np.arange(175)]
print('independent face best',float(best_scores.mean()),'zero',int(np.sum(best_scores==0)),'below.1',int(np.sum(best_scores<.1)),'unique source',len(set(best_for_face)))
missing_codes=sorted(set(c for c,_,_ in main_parts)-set(main_parts[i][0] for i in best_for_face))
print('independent missing codes',len(missing_codes),[(c,allzones[c]['name']) for c in missing_codes])
for j in np.argsort(best_scores)[:25]:
    print('face worst',main_faces[j],main_parts[best_for_face[j]][:2],round(float(best_scores[j]),3))
for face_id in (9,10,49,54,56,59,60,70,88,147,154,172,173):
    j=main_faces.index(face_id)
    best=np.argsort(scores[:,j])[-8:][::-1]
    print('face candidates',face_id,[(main_parts[i][:2],round(float(scores[i,j]),3)) for i in best])
for r in rows:
    if old[(r['code'],r['part'])]!=r['face']: print('change',r['code'],r['part'],old[(r['code'],r['part'])],r['face'],r['iou'])
Path('output/optimized_mapping.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
