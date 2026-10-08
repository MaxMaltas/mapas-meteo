import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image, ImageDraw
from meteo_pipeline.alert_map import _planar_faces, read_alert_shape

root = Path(__file__).resolve().parents[1]
shot = Image.open('C:/Users/ARUBAI~1/AppData/Local/Temp/codex-clipboard-a6e8ac38-3d1e-4780-a6bd-94c728eb4a3f.png').convert('RGB')
our = Image.open(root/'output/alertas_warped_2026-10-02.png').convert('RGBA')
faces = _planar_faces(read_alert_shape(root/'data/alert_map_template/DOMDocument.xml','Capa_4'))
ref = json.loads((root/'output/warped_reference.json').read_text(encoding='utf8'))
by_face = {row['face']: row for row in ref['assignments']}

def level(rgb):
    r,g,b=rgb[:3]
    if r>240 and g>240 and b<50: return 'yellow'
    if r>180 and g<140 and b<70: return 'orange'
    if r>150 and g<80 and b<80: return 'red'
    if r>130 and 40<g<100 and b<90 and r>1.8*g: return 'red'
    if r>180 and 120<g<205 and b<130 and r>g*1.15: return 'orange'
    if r>180 and 180<g<250 and b<130 and abs(r-g)<35: return 'yellow'
    return 'green'

for face_index, poly in enumerate(faces):
    left=min(x for x,y in poly);right=max(x for x,y in poly)
    top=min(y for x,y in poly);bottom=max(y for x,y in poly)
    counts={name:0 for name in ('green','yellow','orange','red')}
    mask=Image.new('1',our.size)
    ImageDraw.Draw(mask).polygon(poly,fill=1)
    for y in range(int(top)+3,int(bottom)-2,5):
        for x in range(int(left)+3,int(right)-2,5):
            if not mask.getpixel((x,y)):
                continue
            sx=round(.53*x-190);sy=round(.49*y+12)
            if 0<=sx<shot.width and 0<=sy<shot.height:
                counts[level(shot.getpixel((sx,sy)))]+=1
    total=sum(counts.values())
    if total<3:continue
    shot_level=max(counts,key=counts.get)
    own = level(our.getpixel((int((left+right)/2),int((top+bottom)/2))))
    if shot_level != own and counts[shot_level]/total>.7:
        row=by_face[face_index]
        print(face_index,row['zone_code'],row['zone_name'],own,shot_level,round(counts[shot_level]/total,2),counts)
