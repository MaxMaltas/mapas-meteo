import json,sys,math
from pathlib import Path
from collections import Counter
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from meteo_pipeline.alert_map import _project
from meteo_pipeline.illustrator_map import read_illustrator_shapes
from tools.build_alert_zone_face_reference import _read_cap_snapshots,_minimum_cost_assignment

SPLIT={
'611101':['Fm57','Fm58'],'611402':['Fm61','Fm214'],'614103':['Fm201','Fm209'],
'645301':['Fm223','Fm224'],'659101':['Fm235','Fm236'],
'663903':['Fm89','Fm217'],'670503':['Fm95','Fm96'],'673702':['Fm106','Fm210'],
'674701':['Fm202','Fm220'],'674901':['Fm111','Fm221'],
'680202':['Fm181','Fm216'],'681301':['Fm115','Fm211'],'694304':['Fm51','Fm215'],
'722801':['Fm148','Fm222'],'733003':['Fm183','Fm213'],'743102':['Fm204','Fm219'],
'754802':['Fm161','Fm218'],'774601':['Fm188','Fm189'],
}
zones=max(_read_cap_snapshots(ROOT/'data/raw/2026-10-01/avisos_cap.data.tar').values(),key=len)
shapes={s.form_id:s for s in read_illustrator_shapes(ROOT/'MAPA_ALERTAS_ILUSTRATOR.ai') if s.layer=='ZONAS AEMET' and s.bounds[0]<1700}
original=np.array(json.loads((ROOT/'output/ai_projection_matrix.json').read_text(encoding='utf8')))
def centroid(poly):
    pts=np.array(poly)
    if len(pts)>1 and np.allclose(pts[0],pts[-1]):pts=pts[:-1]
    a=pts; b=np.roll(pts,-1,axis=0)
    cross=a[:,0]*b[:,1]-b[:,0]*a[:,1]
    if abs(cross.sum())<1e-5:return pts.mean(0)
    return ((a+b)*cross[:,None]).sum(0)/(3*cross.sum())
def area(poly):
    p=np.array(poly);q=np.roll(p,-1,axis=0)
    return abs((p[:,0]*q[:,1]-q[:,0]*p[:,1]).sum()/2)
def source(poly,matrix):
    return np.array([[*_project(lat,lon),1] for lat,lon in poly])@matrix
def center(shape):
    return centroid(max(shape.polygons,key=area))

# The major matched components are spatial controls. Tiny detached pieces are
# excluded from the warp because their raster centroids can be unstable.
controls=[]
for code,ids in SPLIT.items():
    if code.startswith(('64','65')):continue
    for i,fid in enumerate(ids):
        shape=shapes[fid]
        if shape.area<100:continue
        poly=source(zones[code]['polygons'][i],original)
        controls.append((centroid(poly),center(shape),code,fid))
ctrl_src=np.array([c[0] for c in controls]);ctrl_dst=np.array([c[1] for c in controls])
resid=ctrl_dst-ctrl_src
print('control residual median',np.median(np.linalg.norm(resid,axis=1)),'max',np.max(np.linalg.norm(resid,axis=1)))
def warp(points):
    d2=((points[:,None,:]-ctrl_src[None,:,:])**2).sum(2)
    near=np.argsort(d2,axis=1)[:,:6]
    weights=1/np.maximum(np.take_along_axis(d2,near,axis=1),100)
    return points+(resid[near]*weights[:,:,None]).sum(1)/weights.sum(1)[:,None]

used={f for fs in SPLIT.values() for f in fs}
output=[]
for group in ['bal','can','main']:
    def group_code(code):return 'bal' if code.startswith('64') else 'can' if code.startswith('65') else 'main'
    def group_shape(fid):
        n=int(fid[2:]);return 'bal' if 223<=n<=230 else 'can' if 232<=n<=245 else 'main'
    codes=[c for c,z in sorted(zones.items()) if not c.endswith('C') and c not in SPLIT and group_code(c)==group]
    ids=[fid for fid in shapes if fid not in used and group_shape(fid)==group]
    print('group',group,len(codes),len(ids))
    if group=='main':assert len(codes)-len(ids)==5
    else:assert len(codes)==len(ids)
    meta=[]
    for code in codes:
        poly=source(zones[code]['polygons'][0],original)
        if group=='main':poly=warp(poly)
        else:
            # The mainland registration does not apply to relocated island insets.
            poly=source(zones[code]['polygons'][0],np.eye(3,2)) if False else poly
        meta.append((centroid(poly),area(poly)))
    scale=1.0
    if group!='main':
        # Affine layout for the island insets is not the mainland fit. Use the
        # project's native geographic projection without the mainland correction.
        meta=[]
        for code in codes:
            poly=np.array([_project(lat,lon) for lat,lon in zones[code]['polygons'][0]])
            meta.append((centroid(poly),area(poly)))
    costs=[]
    for src_center,src_area in meta:
        row=[]
        for fid in ids:
            sh=shapes[fid]
            distance=float(np.linalg.norm(src_center-center(sh)))
            ratio=abs(math.log(max(src_area,1)/max(sh.area,1)))
            row.append((distance/40)**2+(ratio/.65)**2)
        row += [7.5]*(len(codes)-len(ids))
        costs.append(row)
    indices=_minimum_cost_assignment(costs)
    for code,choice,row in zip(codes,indices,costs):
        ranked=sorted(((round(float(v),2),ids[j]) for j,v in enumerate(row[:len(ids)])))[:4]
        assigned=ids[choice] if choice<len(ids) else None
        output.append({'code':code,'name':zones[code]['name'],'form_id':assigned,'cost':round(float(row[choice]),2),'top':ranked,'group':group})
    print('missing',[(r['code'],r['name'],r['top']) for r in output if r['group']==group and r['form_id'] is None])
    print('worst',[(r['code'],r['form_id'],r['cost']) for r in sorted((r for r in output if r['group']==group),key=lambda r:r['cost'],reverse=True)[:15]])
(ROOT/'output/illustrator_remaining_assignment.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf8')
from PIL import Image, ImageDraw, ImageFont
image=Image.open(ROOT/'output/illustrator_zone_inventory.png').convert('RGB')
draw=ImageDraw.Draw(image)
font=ImageFont.truetype('arial.ttf',16)
for item in output:
    if item['form_id'] is not None:continue
    poly=warp(source(zones[item['code']]['polygons'][0],original))
    points=[tuple(point) for point in poly]
    draw.line(points+[points[0]],fill='#e00000',width=4)
    x,y=centroid(poly)
    draw.text((float(x),float(y)),item['code'],fill='#9c0000',font=font,anchor='mm',stroke_width=3,stroke_fill='white')
image.save(ROOT/'output/illustrator_missing_zones_overlay.png')
