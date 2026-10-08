import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np

from meteo_pipeline.alert_map import _planar_faces, read_alert_shape
from tools.build_alert_zone_face_reference import _minimum_cost_assignment, _read_cap_snapshots


def area_centroid(points):
    closed = list(points)
    if closed[0] != closed[-1]:
        closed.append(closed[0])
    total = cx = cy = 0.0
    for (x1, y1), (x2, y2) in zip(closed, closed[1:]):
        cross = x1 * y2 - x2 * y1
        total += cross
        cx += (x1 + x2) * cross
        cy += (y1 + y2) * cross
    if abs(total) < 1e-9:
        return np.mean(np.array(points), axis=0)
    return np.array([cx / (3 * total), cy / (3 * total)])


snap = _read_cap_snapshots(Path('data/raw/2026-10-01/avisos_cap.data.tar'))
zones = max(snap.values(), key=len)
parts = [(c, k, poly) for c, z in sorted(zones.items()) if not c.endswith('C') for k, poly in enumerate(z['polygons']) if not (c == '694304' and k == 1)]
faces = _planar_faces(read_alert_shape(Path('data/alert_map_template/DOMDocument.xml'), 'Capa_4'))
main_parts = [(c, k, poly) for c, k, poly in parts if not c.startswith(('64', '65', '78', '79'))]
main_faces = [i for i in range(len(faces)) if i not in list(range(22, 30)) + list(range(181, 196)) + [198, 199]]
assert len(main_parts) == len(main_faces) == 175
source = np.array([area_centroid([(lon, lat) for lat, lon in p]) for _, _, p in main_parts])
target = np.array([area_centroid(faces[i]) for i in main_faces])
matrix = np.array([[90.62040288074171, 7.127272113678237], [3.8106931378317377, -117.54813366969704], [1087.9473551853685, 5222.066708413059]])
source_h = np.column_stack((source, np.ones(len(source))))
for iteration in range(20):
    projected = source_h @ matrix
    costs = ((projected[:, None, :] - target[None, :, :]) ** 2).sum(2)
    assignment = _minimum_cost_assignment(costs.tolist())
    residual = target[assignment] - projected
    new_matrix = np.linalg.lstsq(source_h, target[assignment], rcond=None)[0]
    print(iteration, np.median(np.linalg.norm(residual, axis=1)), np.max(np.linalg.norm(residual, axis=1)), np.sum(np.linalg.norm(residual, axis=1)>50))
    if np.max(np.abs(new_matrix-matrix)) < 0.001:
        break
    matrix = new_matrix
print('matrix', matrix)
for idx in np.argsort(np.linalg.norm(residual, axis=1))[-30:]:
    print(main_parts[idx][0:2], zones[main_parts[idx][0]]['name'], main_faces[assignment[idx]], round(float(np.linalg.norm(residual[idx])), 1))
