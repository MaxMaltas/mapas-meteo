import json, math, sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from meteo_pipeline.alert_map import _project
from meteo_pipeline.illustrator_map import read_illustrator_shapes
from tools.build_alert_zone_face_reference import _read_cap_snapshots
zones=max(_read_cap_snapshots(ROOT/'data/raw/2026-10-01/avisos_cap.data.tar').values(),key=len)
shapes=[s for s in read_illustrator_shapes(ROOT/'MAPA_ALERTAS_ILUSTRATOR.ai') if s.layer=='ZONAS AEMET' and s.bounds[0]<1700]
matrix=np.array(json.loads((ROOT/'output/ai_projection_matrix.json').read_text(encoding='utf-8')))
def area(p):
    return abs(sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(p,p[1:]+p[:1]))/2)
def center(p):
    return np.array([sum(x for x,y in p)/len(p),sum(y for x,y in p)/len(p)])
for code,z in sorted(zones.items()):
    if code.endswith('C') or len(z['polygons'])!=2 or code.startswith(('64','65')):continue
    parts=[]
    for poly in z['polygons']:
        p=np.array([[*_project(lat,lon),1] for lat,lon in poly])@matrix
        parts.append((center(p.tolist()),area(p.tolist())))
    choices=[]
    for first in shapes:
        fc=np.array([(first.bounds[0]+first.bounds[2])/2,(first.bounds[1]+first.bounds[3])/2])
        fd=float(np.linalg.norm(fc-parts[0][0]))
        ar=abs(math.log(max(first.area,1)/max(parts[0][1],1)))
        if fd>120 or ar>1.6:continue
        for second in shapes:
            if second.form_id==first.form_id:continue
            sc=np.array([(second.bounds[0]+second.bounds[2])/2,(second.bounds[1]+second.bounds[3])/2])
            sd=float(np.linalg.norm(sc-parts[1][0]))
            sr=abs(math.log(max(second.area,1)/max(parts[1][1],1)))
            rel=float(np.linalg.norm((sc-fc)-(parts[1][0]-parts[0][0])))
            if sd>120 or sr>1.6 or rel>80:continue
            cost=(fd/55)**2+(sd/55)**2+(rel/25)**2+(ar/.5)**2+(sr/.5)**2
            choices.append((cost,first.form_id,second.form_id,round(fd),round(sd),round(rel),round(ar,2),round(sr,2)))
    choices.sort()
    print(code,z['name'],'part_area',round(parts[0][1]),round(parts[1][1]))
    print(' ',choices[:6])
