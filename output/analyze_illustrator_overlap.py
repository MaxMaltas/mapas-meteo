from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from meteo_pipeline.illustrator_map import read_illustrator_shapes
from meteo_pipeline.alert_map import _planar_faces, read_alert_shape


def mask(polygons):
    image = Image.new('1', (480, 270))
    draw = ImageDraw.Draw(image)
    for polygon in polygons:
        draw.polygon([(x/4, y/4) for x, y in polygon], fill=1)
    return np.asarray(image, dtype=bool)


shapes = [s for s in read_illustrator_shapes(ROOT/'MAPA_ALERTAS_ILUSTRATOR.ai') if s.layer == 'ZONAS AEMET' and s.bounds[0] < 1700]
faces = _planar_faces(read_alert_shape(ROOT/'data/alert_map_template/DOMDocument.xml', 'Capa_4'))
face_masks = [mask([f]) for f in faces]
rows = []
for shape in shapes:
    sm = mask(shape.polygons)
    sa = sm.sum()
    scores = []
    for i, fm in enumerate(face_masks):
        overlap = np.logical_and(sm, fm).sum()
        if overlap:
            iou = overlap/(sa+fm.sum()-overlap)
            scores.append((float(iou), i))
    scores.sort(reverse=True)
    rows.append({'form_id':shape.form_id,'top_faces':[{'face':i,'iou':round(score,3)} for score,i in scores[:3]]})

dest=ROOT/'output/illustrator_fla_overlap.json'
dest.write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')
for row in sorted(rows,key=lambda x:x['top_faces'][0]['iou'] if x['top_faces'] else 0)[:30]:
    print(row)
print('>=0.7',sum(bool(r['top_faces']) and r['top_faces'][0]['iou']>=0.7 for r in rows),'of',len(rows))
