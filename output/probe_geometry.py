import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from tools.build_alert_zone_face_reference import _read_cap_snapshots, _minimum_cost_assignment
from meteo_pipeline.alert_map import _planar_faces, read_alert_shape, _polygon_centroid, _bounds

snap = _read_cap_snapshots(Path('data/raw/2026-10-01/avisos_cap.data.tar'))
allzones = max(snap.values(), key=len)
items = [(c, i, p) for c,z in sorted(allzones.items()) if not c.endswith('C') for i,p in enumerate(z['polygons']) if not (c=='694304' and i==1)]
faces = _planar_faces(read_alert_shape(Path('data/alert_map_template/DOMDocument.xml'), 'Capa_4'))
src = np.array([_polygon_centroid([(lon,lat) for lat,lon in p]) for c,i,p in items])
dst = np.array([_polygon_centroid(p) for p in faces])
# Separate islands / autonomous cities by source code and observed layout bounding boxes.
src_group = [ 'can' if c.startswith('65') else 'bal' if c.startswith('64') else c[:2] if c.startswith(('78','79')) else 'main' for c,_,_ in items]
dst_group = ['can' if x < 610 and y > 840 else 'bal' if x>1300 and y>490 else '78' if 700<x<750 and y>960 else '79' if x>900 and y>1000 else 'main' for x,y in dst]
from collections import Counter
print(Counter(src_group), Counter(dst_group))
mapping={}
for group in sorted(set(src_group)):
    si=[i for i,g in enumerate(src_group) if g==group]; di=[i for i,g in enumerate(dst_group) if g==group]
    if len(si)!=len(di):continue
    s=src[si]; d=dst[di]
    sn=np.column_stack((s,np.ones(len(si))))
    # Initial bounds fit; eastern inclination of editorial layout.
    if group=='main':
        matrix=np.array([[86.69407537,4.44575250],[13.81072779,-115.0],[650.,5100.]])
    else:
        scale=(d.max(0)-d.min(0))/np.maximum(0.001,s.max(0)-s.min(0))
        scale[1]*=-1
        matrix=np.array([[scale[0],0],[0,scale[1]],d.mean(0)-s.mean(0)*scale])
    for iteration in range(40):
        projected=sn@matrix
        costs=((projected[:,None,:]-d[None,:,:])**2).sum(2)
        assigned=_minimum_cost_assignment(costs.tolist())
        newmatrix=np.linalg.lstsq(sn,d[assigned],rcond=None)[0]
        delta=np.max(np.abs(newmatrix-matrix));matrix=newmatrix
        if delta<0.001:break
    errors=np.sqrt(((sn@matrix-d[assigned])**2).sum(1))
    print(group, len(si), 'iterations',iteration,'mean',errors.mean(), 'max',errors.max(),'matrix',matrix.tolist())
    for i,j,e in zip(si,assigned,errors):mapping[i]=di[j]
    for k in np.argsort(errors)[-8:]:
        print(' worst',items[si[k]][:2],di[assigned[k]], round(errors[k],1),allzones[items[si[k]][0]]['name'])
for i in mapping:
    c,part,_=items[i]
    if c.startswith(('6740','6454','6222','6244','7712','7746','7703','7330','6104')):
        print(c,part,allzones[c]['name'],mapping[i])
import json
Path('output/geometry_probe_mapping.json').write_text(json.dumps([{'code':items[i][0],'part':items[i][1],'face':f} for i,f in mapping.items()]),encoding='utf-8')
