from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import tarfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from meteo_pipeline.alert_map import (  # noqa: E402
    _bounds,
    _planar_faces,
    _polygon_centroid,
    _project,
    read_alert_shape,
)


CAP_NAMESPACE = {"cap": "urn:oasis:names:tc:emergency:cap:1.2"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Construye una referencia estable entre las caras del mapa Animate "
            "y las zonas terrestres AEMET presentes en un paquete CAP completo."
        )
    )
    parser.add_argument("--cap", type=Path, required=True)
    parser.add_argument(
        "--template",
        type=Path,
        default=ROOT / "data" / "alert_map_template" / "DOMDocument.xml",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "config" / "alert_zone_faces.reference.json",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    faces = _planar_faces(read_alert_shape(args.template, "Capa_4"))
    snapshots = _read_cap_snapshots(args.cap)
    candidates = []
    for sent, zones in snapshots.items():
        land_zones = {code: zone for code, zone in zones.items() if not code.endswith("C")}
        part_count = sum(len(zone["polygons"]) for zone in land_zones.values())
        if part_count == len(faces):
            candidates.append((sent, zones))
    if not candidates:
        counts = sorted(
            {
                sum(
                    len(zone["polygons"])
                    for code, zone in zones.items()
                    if not code.endswith("C")
                )
                for zones in snapshots.values()
            }
        )
        raise SystemExit(
            f"No hay una instantánea CAP con {len(faces)} fragmentos terrestres; "
            f"recuentos encontrados: {counts}"
        )

    sent, all_zones = max(candidates, key=lambda item: item[0])
    zones = {
        code: zone for code, zone in all_zones.items() if not code.endswith("C")
    }
    marine_zones = {
        code: zone for code, zone in all_zones.items() if code.endswith("C")
    }
    parts = []
    for code in sorted(zones):
        zone = zones[code]
        for part_index, polygon in enumerate(zone["polygons"]):
            projected = [_project(latitude, longitude) for latitude, longitude in polygon]
            parts.append(
                {
                    "zone_code": code,
                    "zone_name": zone["name"],
                    "part": part_index,
                    "projected_centroid": _polygon_centroid(projected),
                    "projected_bounds": _bounds(projected),
                }
            )

    face_centroids = [_polygon_centroid(face) for face in faces]
    costs = [
        [
            _squared_distance(part["projected_centroid"], face_centroid)
            for face_centroid in face_centroids
        ]
        for part in parts
    ]
    assignment = _minimum_cost_assignment(costs)

    by_face = []
    for part_index, face_index in enumerate(assignment):
        part = parts[part_index]
        distance = math.sqrt(costs[part_index][face_index])
        by_face.append(
            {
                "face": face_index,
                "zone_code": part["zone_code"],
                "zone_name": part["zone_name"],
                "part": part["part"],
                "face_centroid": _round_pair(face_centroids[face_index]),
                "face_bounds": _round_values(_bounds(faces[face_index])),
                "projected_centroid": _round_pair(part["projected_centroid"]),
                "distance_px": round(distance, 3),
            }
        )

    by_face.sort(key=lambda item: item["face"])
    document = {
        "schema_version": 1,
        "purpose": "reference_only_not_yet_used_by_renderer",
        "template": _display_path(args.template),
        "template_sha256": hashlib.sha256(args.template.read_bytes()).hexdigest(),
        "source_cap": _display_path(args.cap),
        "source_cap_snapshot": sent,
        "face_count": len(faces),
        "land_zone_count": len(zones),
        "marine_zone_count": len(marine_zones),
        "polygon_part_count": len(parts),
        "marine_polygon_part_count": sum(
            len(zone["polygons"]) for zone in marine_zones.values()
        ),
        "marine_zone_policy": "preserve_codes_ending_in_C_as_independent_zones",
        "assignment_method": "global_minimum_projected_centroid_distance",
        "assignments": by_face,
        "marine_zones": [
            {
                "zone_code": code,
                "zone_name": marine_zones[code]["name"],
                "polygons": [
                    [[round(latitude, 5), round(longitude, 5)] for latitude, longitude in polygon]
                    for polygon in marine_zones[code]["polygons"]
                ],
            }
            for code in sorted(marine_zones)
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"{args.output}: {len(by_face)} caras, {len(zones)} zonas terrestres, "
        f"{len(marine_zones)} zonas marítimas, instantánea {sent}"
    )


def _read_cap_snapshots(cap_path: Path) -> dict[str, dict[str, dict]]:
    snapshots: dict[str, dict[str, dict]] = defaultdict(dict)
    with tarfile.open(cap_path, mode="r:*") as archive:
        for member in archive.getmembers():
            if not member.isfile() or not member.name.lower().endswith(".xml"):
                continue
            extracted = archive.extractfile(member)
            if not extracted:
                continue
            root = ET.fromstring(extracted.read())
            sent = root.findtext("cap:sent", default="", namespaces=CAP_NAMESPACE)
            for info in root.findall("cap:info", CAP_NAMESPACE):
                language = info.findtext(
                    "cap:language", default="", namespaces=CAP_NAMESPACE
                )
                if not language.lower().startswith("es"):
                    continue
                for area in info.findall("cap:area", CAP_NAMESPACE):
                    name = area.findtext(
                        "cap:areaDesc", default="", namespaces=CAP_NAMESPACE
                    )
                    polygons = _area_polygons(area)
                    for geocode in area.findall("cap:geocode", CAP_NAMESPACE):
                        value_name = geocode.findtext(
                            "cap:valueName", default="", namespaces=CAP_NAMESPACE
                        )
                        if "Meteoalerta zona" not in value_name:
                            continue
                        code = geocode.findtext(
                            "cap:value", default="", namespaces=CAP_NAMESPACE
                        )
                        existing = snapshots[sent].get(code)
                        candidate = {"name": name, "polygons": polygons}
                        if existing and existing != candidate:
                            raise ValueError(
                                f"La zona {code} tiene geometrías distintas en {sent}"
                            )
                        snapshots[sent][code] = candidate
    return snapshots


def _area_polygons(area: ET.Element) -> list[list[tuple[float, float]]]:
    result = []
    for polygon in area.findall("cap:polygon", CAP_NAMESPACE):
        points = []
        for pair in (polygon.text or "").split():
            latitude_text, longitude_text = pair.split(",", 1)
            points.append((float(latitude_text), float(longitude_text)))
        if len(points) >= 3:
            result.append(points)
    return result


def _minimum_cost_assignment(costs: list[list[float]]) -> list[int]:
    """Hungarian algorithm for a square cost matrix."""
    size = len(costs)
    if not size or any(len(row) != size for row in costs):
        raise ValueError("La matriz de costes debe ser cuadrada y no vacía")

    u = [0.0] * (size + 1)
    v = [0.0] * (size + 1)
    matched_row = [0] * (size + 1)
    previous_column = [0] * (size + 1)

    for row in range(1, size + 1):
        matched_row[0] = row
        current_column = 0
        minimum = [float("inf")] * (size + 1)
        used = [False] * (size + 1)
        while True:
            used[current_column] = True
            current_row = matched_row[current_column]
            delta = float("inf")
            next_column = 0
            for column in range(1, size + 1):
                if used[column]:
                    continue
                reduced = (
                    costs[current_row - 1][column - 1]
                    - u[current_row]
                    - v[column]
                )
                if reduced < minimum[column]:
                    minimum[column] = reduced
                    previous_column[column] = current_column
                if minimum[column] < delta:
                    delta = minimum[column]
                    next_column = column
            for column in range(size + 1):
                if used[column]:
                    u[matched_row[column]] += delta
                    v[column] -= delta
                else:
                    minimum[column] -= delta
            current_column = next_column
            if matched_row[current_column] == 0:
                break
        while True:
            next_column = previous_column[current_column]
            matched_row[current_column] = matched_row[next_column]
            current_column = next_column
            if current_column == 0:
                break

    assignment = [-1] * size
    for column in range(1, size + 1):
        assignment[matched_row[column] - 1] = column - 1
    return assignment


def _squared_distance(
    first: tuple[float, float], second: tuple[float, float]
) -> float:
    return (first[0] - second[0]) ** 2 + (first[1] - second[1]) ** 2


def _round_pair(values: tuple[float, float]) -> list[float]:
    return [round(value, 3) for value in values]


def _round_values(values: tuple[float, ...]) -> list[float]:
    return [round(value, 3) for value in values]


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return str(resolved)


if __name__ == "__main__":
    main()
