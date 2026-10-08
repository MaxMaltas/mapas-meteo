import copy
import json
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meteo_pipeline.alert_map import _bounds, _planar_faces, _polygon_centroid, _project, read_alert_shape, render_alert_map
from meteo_pipeline.alerts import summarise_cap_by_zone
from tools.build_alert_zone_face_reference import _read_cap_snapshots

root = Path(__file__).resolve().parents[1]
template = root / 'data/alert_map_template/DOMDocument.xml'
old = json.loads((root / 'config/alert_zone_faces.reference.json').read_text(encoding='utf8'))
ref = copy.deepcopy(old)
faces = _planar_faces(read_alert_shape(template, 'Capa_4'))
snapshot = max(_read_cap_snapshots(root / 'data/raw/2026-10-01/avisos_cap.data.tar').values(), key=len)
main = json.loads((root / 'output/warped_face_candidates.json').read_text(encoding='utf8'))
by_face = {row['face']: (row['code'], row['part']) for row in main}
by_face[171] = ('611803', 0)  # PDF provincial: inland Nevada y Alpujarras, not coastal Granada.
by_face[107] = ('670503', 1)  # Small southern fragment of Ávila.
by_face[49] = ('754802', 1)  # Tiny Bizkaia-interior fragment by the Álava border.
for face_index in (87, 90, 94, 100, 176):
    # Fragmented Galicia: preserve the 2017 provincial-zone placement where
    # planar overlap alone conflates adjacent geographic polygons.
    original = next(item for item in old['assignments'] if item['face'] == face_index)
    by_face[face_index] = (original['zone_code'], original['part'])
for row in old['assignments']:
    if 22 <= row['face'] <= 29 or row['face'] in (198, 199):
        by_face[row['face']] = (row['zone_code'], row['part'])
by_face.update({
    181: ('659101', 0), 182: ('659101', 1), 183: ('659201', 0),
    184: ('659602', 0), 185: ('659603', 0), 186: ('659601', 0),
    187: ('659401', 0), 188: ('659001', 0), 189: ('659004', 0),
    190: ('659003', 0), 191: ('659303', 0), 192: ('659302', 0),
    193: ('659304', 0), 194: ('659304', 0), 195: ('659501', 0),
})
assert sorted(by_face) == list(range(200))
assignments = []
for face_index, (code, part) in sorted(by_face.items()):
    poly = snapshot[code]['polygons'][part]
    projected = [_project(lat, lon) for lat, lon in poly]
    assignments.append({
        'face': face_index, 'zone_code': code, 'zone_name': snapshot[code]['name'], 'part': part,
        'face_centroid': list(_polygon_centroid(faces[face_index])),
        'face_bounds': list(_bounds(faces[face_index])),
        'projected_centroid': list(_polygon_centroid(projected)),
    })
ref['assignments'] = assignments
ref['purpose'] = 'unverified_provisional_preview_only'
preview_ref = root / 'output/warped_reference.json'
preview_ref.write_text(json.dumps(ref, ensure_ascii=False, indent=2), encoding='utf8')
raw = (root / 'data/raw/2026-10-02/avisos_cap.data.tar').read_bytes()
as_of = datetime.fromisoformat(json.loads((root / 'data/generated/2026-10-02/meteo.json').read_text(encoding='utf8'))['generated_at'])
zones = summarise_cap_by_zone(raw, date(2026, 10, 2), as_of=as_of)['zones']
path = root / 'output/alertas_warped_2026-10-02.png'
render_alert_map(template, zones, path, zone_reference=preview_ref)
print(path)
