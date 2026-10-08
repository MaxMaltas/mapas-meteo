from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.build_alert_zone_face_reference import _read_cap_snapshots
from meteo_pipeline.illustrator_map import read_illustrator_shapes
from meteo_pipeline.alert_map import _project

zones=max(_read_cap_snapshots(ROOT/'data/raw/2026-10-01/avisos_cap.data.tar').values(),key=len)
shapes=[s for s in read_illustrator_shapes(ROOT/'MAPA_ALERTAS_ILUSTRATOR.ai') if s.layer=='ZONAS AEMET' and s.bounds[0]<1700]
for code,z in sorted(zones.items()):
    if code.endswith('C') or len(z['polygons'])<2:continue
    print(code,z['name'])
    for part,polygon in enumerate(z['polygons']):
        lat=sum(p[0] for p in polygon)/len(polygon)
        lon=sum(p[1] for p in polygon)/len(polygon)
        px,py=_project(lat,lon)
        nearest=sorted((( (px-(s.bounds[0]+s.bounds[2])/2)**2+(py-(s.bounds[1]+s.bounds[3])/2)**2)**.5,s.form_id) for s in shapes)[:5]
        print(' ',part,'geo',round(lat,3),round(lon,3),'projected',round(px),round(py),'nearest',[(fid,round(d)) for d,fid in nearest])
