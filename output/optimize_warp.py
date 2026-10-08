"""Exploratory non-rigid registration of CAP zones to the fixed Animate faces."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
from PIL import Image, ImageDraw

from meteo_pipeline.alert_map import _planar_faces, read_alert_shape
from tools.build_alert_zone_face_reference import _read_cap_snapshots

root = Path(__file__).resolve().parents[1]
zones = max(_read_cap_snapshots(root/'data/raw/2026-10-01/avisos_cap.data.tar').values(), key=len)
parts = [(c,k,p) for c,z in sorted(zones.items()) if not c.endswith('C') for k,p in enumerate(z['polygons']) if not c.startswith(('64','65','78','79')) and not (c=='694304' and k==1)]
faces = _planar_faces(read_alert_shape(root/'data/alert_map_template/DOMDocument.xml','Capa_4'))
face_ids = [i for i in range(200) if i not in list(range(22,30))+list(range(181,196))+[198,199]]
assert len(parts)==len(face_ids)==175
matrix = np.array([[90.62040288074171,7.127272113678237],[3.8106931378317377,-117.54813366969704],[1087.9473551853685,5222.066708413059]])

def centroid(points):
    pts=np.array(points,dtype=float)
    p1=pts[:-1];p2=pts[1:]
    cross=p1[:,0]*p2[:,1]-p2[:,0]*p1[:,1]
    area=cross.sum()
    if abs(area)<1e-8:return pts.mean(axis=0)
    return np.array([((p1[:,0]+p2[:,0])*cross).sum(),((p1[:,1]+p2[:,1])*cross).sum()])/(3*area)

def project(poly):
    return np.column_stack(([lon for lat,lon in poly],[lat for lat,lon in poly],np.ones(len(poly))))@matrix

def render(points):
    im=Image.new('1',(480,270));ImageDraw.Draw(im).polygon([(round(x/4),round(y/4)) for x,y in points],fill=1)
    return np.asarray(im,dtype=bool)

targets=np.array([render(faces[i]) for i in face_ids])
target_centers=np.array([centroid(faces[i]) for i in face_ids])
projected=[project(p) for _,_,p in parts]
source_centers=np.array([centroid(p) for p in projected])

def iou_matrix(source_masks):
    source_areas=np.array([m.sum() for m in source_masks]);target_areas=np.array([m.sum() for m in targets])
    scores=np.zeros((len(source_masks),len(targets)))
    for i,sm in enumerate(source_masks):
        for j,tm in enumerate(targets):
            intersection=np.logical_and(sm,tm).sum()
            union=source_areas[i]+target_areas[j]-intersection
            scores[i,j]=intersection/union if union else 0
    return scores

warped=projected
for iteration in range(4):
    scores=iou_matrix([render(p) for p in warped])
    by_source=scores.argmax(axis=1);by_face=scores.argmax(axis=0)
    anchors=[]
    for i,j in enumerate(by_source):
        if by_face[j]!=i or scores[i,j]<.38:continue
        margin=scores[i,j]-np.partition(scores[i],-2)[-2]
        if margin<.07:continue
        anchors.append((i,j,float(scores[i,j])))
    best=scores[by_face,np.arange(175)]
    missed=sorted({c for c,_,_ in parts}-{parts[i][0] for i in by_face})
    print('iteration',iteration,'anchors',len(anchors),'mean_face_iou',round(float(best.mean()),3),'weak_faces',int((best<.1).sum()),'missing_codes',len(missed))
    if iteration==3:break
    control_src=np.array([source_centers[i] for i,j,s in anchors])
    control_dst=np.array([target_centers[j] for i,j,s in anchors])
    if len(control_src)<30:break
    displacement=control_dst-control_src
    def warp(points):
        d2=((points[:,None,:]-control_src[None,:,:])**2).sum(2)
        nearest=np.argsort(d2,axis=1)[:,:8]
        weights=1/np.maximum(np.take_along_axis(d2,nearest,axis=1),64)
        local=displacement[nearest]
        return points+(local*weights[:,:,None]).sum(1)/weights.sum(1)[:,None]
    warped=[warp(p) for p in projected]

rows=[]
for j,i in enumerate(by_face):
    choices=np.argsort(scores[:,j])[-3:][::-1]
    rows.append({'face':face_ids[j],'code':parts[i][0],'name':zones[parts[i][0]]['name'],'part':parts[i][1],'iou':round(float(scores[i,j]),3),'alternatives':[(parts[k][0],parts[k][1],round(float(scores[k,j]),3)) for k in choices]})
print('missing',[(c,zones[c]['name']) for c in missed])
for code in missed:
    for i,(c,k,poly) in enumerate(parts):
        if c!=code:continue
        best_faces=np.argsort(scores[i])[-6:][::-1]
        print('missing candidates',code,k,[(face_ids[j],round(float(scores[i,j]),3),parts[by_face[j]][0]) for j in best_faces])
print('weak',*[row for row in rows if row['iou']<.1],sep='\n')
(root/'output/warped_face_candidates.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')
