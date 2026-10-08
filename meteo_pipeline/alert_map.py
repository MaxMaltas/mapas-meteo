from __future__ import annotations

import hashlib
import json
import re
import zipfile
from math import atan2
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET

from PIL import Image, ImageChops, ImageDraw


XFL_NAMESPACE = {"xfl": "http://ns.adobe.com/xfl/2008/"}
EDGE_COMMAND = re.compile(r"([!|])\s*(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)")
LEVEL_COLORS = {
    "green": "#00CC66",
    "yellow": "#FEFF02",
    "orange": "#E7711D",
    "red": "#CC0000",
}
LEVEL_RANK = {"green": 0, "yellow": 1, "orange": 2, "red": 3}

# The alert polygons use geographic coordinates. The Animate artwork is an
# oblique editorial projection, with Canarias moved into an inset. These two
# affine transforms are calibrated against the coastline vertices in the FLA.
MAINLAND_AFFINE = (86.69407537, 13.81072779, 695.30566962, 4.44575250, -127.31446600, 5618.33830288)
CANARY_AFFINE = (55.94, 0.0, 1303.6012, 0.0, -67.0, 2808.58)


@dataclass(frozen=True)
class EdgePath:
    points: tuple[tuple[float, float], ...]
    fill_left: int | None
    fill_right: int | None
    stroke: int | None


def read_alert_shape(fla_path: Path, layer_name: str, frame: int | None = None) -> list[EdgePath]:
    """Read the editable vector paths from an Adobe Animate FLA/XFL layer."""
    if fla_path.suffix.lower() == ".xml":
        root = ET.parse(fla_path).getroot()
    else:
        with zipfile.ZipFile(fla_path) as archive:
            root = ET.fromstring(archive.read("DOMDocument.xml"))

    layers = root.findall(".//xfl:DOMLayer", XFL_NAMESPACE)
    layer = next((item for item in layers if item.get("name") == layer_name), None)
    if layer is None:
        raise ValueError(f"No existe la capa {layer_name!r} en {fla_path}")

    frames = layer.findall("./xfl:frames/xfl:DOMFrame", XFL_NAMESPACE)
    if frame is None:
        selected_frame = frames[0] if frames else None
    else:
        selected_frame = next(
            (item for item in frames if int(item.get("index", "0")) == frame), None
        )
    if selected_frame is None:
        raise ValueError(f"No existe el fotograma {frame!r} en la capa {layer_name!r}")

    result: list[EdgePath] = []
    for edge in selected_frame.findall(".//xfl:Edge", XFL_NAMESPACE):
        fill_left = _optional_int(edge.get("fillStyle0"))
        fill_right = _optional_int(edge.get("fillStyle1"))
        stroke = _optional_int(edge.get("strokeStyle"))
        current: list[tuple[float, float]] = []
        for match in EDGE_COMMAND.finditer(edge.get("edges", "")):
            command, raw_x, raw_y = match.groups()
            point = (float(raw_x) / 20.0, float(raw_y) / 20.0)
            if command == "!":
                if len(current) > 1:
                    result.append(EdgePath(tuple(current), fill_left, fill_right, stroke))
                current = [point]
            elif current:
                current.append(point)
        if len(current) > 1:
            result.append(EdgePath(tuple(current), fill_left, fill_right, stroke))
    return result


def connected_component_bounds(paths: Iterable[EdgePath]) -> list[tuple[int, tuple[float, float, float, float]]]:
    """Return component sizes/bounds; useful for validating a changed FLA template."""
    adjacency: dict[tuple[float, float], set[tuple[float, float]]] = defaultdict(set)
    for path in paths:
        for first, second in zip(path.points, path.points[1:]):
            adjacency[first].add(second)
            adjacency[second].add(first)

    unseen = set(adjacency)
    result: list[tuple[int, tuple[float, float, float, float]]] = []
    while unseen:
        seed = unseen.pop()
        stack = [seed]
        points = [seed]
        while stack:
            point = stack.pop()
            for neighbour in adjacency[point]:
                if neighbour in unseen:
                    unseen.remove(neighbour)
                    stack.append(neighbour)
                    points.append(neighbour)
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        result.append((len(points), (min(xs), min(ys), max(xs), max(ys))))
    return sorted(result, reverse=True)


def render_alert_map(
    template_xml: Path,
    zones: Iterable[dict],
    output_path: Path,
    *,
    width: int = 1920,
    height: int = 1080,
    zone_reference: Path | None = None,
) -> None:
    """Render a transparent PNG using the vector artwork from MAPA_ALERTAS.fla."""
    base_paths = read_alert_shape(template_xml, "Capa_4")
    outline_paths = read_alert_shape(template_xml, "linea_sobre", frame=5)

    faces = _planar_faces(base_paths)
    zone_list = list(zones)
    result = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(result)
    marine_outlines: list[list[tuple[float, float]]] = []
    if zone_reference is not None:
        reference = _load_zone_reference(zone_reference, template_xml, len(faces))
        levels = _levels_by_zone(zone_list)
        known_codes = {
            item["zone_code"] for item in reference["assignments"]
        } | {item["zone_code"] for item in reference["marine_zones"]}
        unknown_codes = sorted(set(levels) - known_codes)
        if unknown_codes:
            raise ValueError(
                "Hay zonas AEMET sin correspondencia en la referencia: "
                + ", ".join(unknown_codes)
            )

        controls = [
            (
                tuple(item["projected_centroid"]),
                tuple(item["face_centroid"]),
            )
            for item in reference["assignments"]
        ]
        for marine in reference["marine_zones"]:
            level = levels.get(marine["zone_code"])
            if not level or level == "green":
                continue
            for geographic_polygon in marine["polygons"]:
                pixels = [
                    _warp_to_template(_project(latitude, longitude), controls)
                    for latitude, longitude in geographic_polygon
                ]
                if len(pixels) >= 3:
                    draw.polygon(pixels, fill=LEVEL_COLORS[level])
                    marine_outlines.append(pixels)

        for item in reference["assignments"]:
            level = levels.get(item["zone_code"], "green")
            draw.polygon(faces[item["face"]], fill=LEVEL_COLORS[level])
    else:
        for polygon in faces:
            draw.polygon(polygon, fill=LEVEL_COLORS["green"])

        assigned_faces: set[int] = set()
        ordered_zones = sorted(
            zone_list, key=lambda item: LEVEL_RANK.get(item.get("level"), 0)
        )
        for zone in ordered_zones:
            level = zone.get("level", "green")
            if level == "green" or level not in LEVEL_COLORS:
                continue
            for geographic_polygon in zone.get("polygons", []):
                pixels = [
                    _project(latitude, longitude)
                    for latitude, longitude in geographic_polygon
                ]
                if len(pixels) >= 3:
                    face_index = _match_face(pixels, faces, assigned_faces)
                    if face_index is not None:
                        assigned_faces.add(face_index)
                        draw.polygon(faces[face_index], fill=LEVEL_COLORS[level])
    outline_draw = ImageDraw.Draw(result)
    for polygon in marine_outlines:
        outline_draw.line(
            polygon + [polygon[0]], fill="#000000", width=1, joint="curve"
        )
    stroke_colors = {1: "#000000", 2: "#666666", 3: "#CCCCCC", 4: "#292424"}
    visible_paths = [
        path for path in base_paths if path.fill_left or path.fill_right
    ] + outline_paths
    for path in visible_paths:
        if path.stroke:
            outline_draw.line(
                path.points,
                fill=stroke_colors.get(path.stroke, "#000000"),
                width=1,
                joint="curve",
            )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.save(output_path)


def _load_zone_reference(
    reference_path: Path, template_xml: Path, face_count: int
) -> dict:
    document = json.loads(reference_path.read_text(encoding="utf-8"))
    if document.get("face_count") != face_count:
        raise ValueError(
            f"La referencia contiene {document.get('face_count')} caras y la plantilla {face_count}"
        )
    digest = hashlib.sha256(template_xml.read_bytes()).hexdigest()
    if document.get("template_sha256") != digest:
        raise ValueError("La referencia de zonas no corresponde a esta plantilla Animate")
    assignments = document.get("assignments", [])
    if sorted(item["face"] for item in assignments) != list(range(face_count)):
        raise ValueError("La referencia no identifica exactamente una vez cada cara terrestre")
    return document


def _levels_by_zone(zones: Iterable[dict]) -> dict[str, str]:
    result: dict[str, str] = {}
    for zone in zones:
        code = str(zone.get("code", ""))
        level = zone.get("level", "green")
        if code and level in LEVEL_COLORS:
            previous = result.get(code, "green")
            if LEVEL_RANK[level] > LEVEL_RANK[previous]:
                result[code] = level
    return result


def _warp_to_template(
    point: tuple[float, float],
    controls: list[tuple[tuple[float, float], tuple[float, float]]],
    neighbour_count: int = 6,
) -> tuple[float, float]:
    """Locally align projected CAP geometry to the fixed editorial map."""
    nearest = sorted(
        (
            (_squared_distance(point, source), source, target)
            for source, target in controls
        ),
        key=lambda item: item[0],
    )[:neighbour_count]
    if nearest and nearest[0][0] < 1e-9:
        return nearest[0][2]
    weighted_x = 0.0
    weighted_y = 0.0
    total_weight = 0.0
    for distance_squared, source, target in nearest:
        weight = 1.0 / max(distance_squared, 25.0)
        weighted_x += (target[0] - source[0]) * weight
        weighted_y += (target[1] - source[1]) * weight
        total_weight += weight
    if not total_weight:
        return point
    return (
        point[0] + weighted_x / total_weight,
        point[1] + weighted_y / total_weight,
    )


def _planar_faces(paths: Iterable[EdgePath]) -> list[list[tuple[float, float]]]:
    adjacency: dict[tuple[float, float], set[tuple[float, float]]] = defaultdict(set)
    for path in paths:
        if not (path.fill_left or path.fill_right):
            continue
        for first, second in zip(path.points, path.points[1:]):
            if first == second:
                continue
            adjacency[first].add(second)
            adjacency[second].add(first)
    ordered = {
        point: sorted(
            neighbours,
            key=lambda neighbour: atan2(neighbour[1] - point[1], neighbour[0] - point[0]),
        )
        for point, neighbours in adjacency.items()
    }
    visited: set[tuple[tuple[float, float], tuple[float, float]]] = set()
    cycles: list[tuple[float, list[tuple[float, float]]]] = []
    for first, neighbours in ordered.items():
        for second in neighbours:
            start = (first, second)
            if start in visited:
                continue
            previous, current = start
            polygon = [previous]
            while (previous, current) not in visited:
                visited.add((previous, current))
                polygon.append(current)
                options = ordered[current]
                incoming_index = options.index(previous)
                following = options[(incoming_index - 1) % len(options)]
                previous, current = current, following
                if (previous, current) == start:
                    break
            if len(polygon) >= 4 and polygon[0] == polygon[-1]:
                area = _signed_area(polygon)
                if abs(area) >= 3.0:
                    cycles.append((area, polygon))
    if not cycles:
        return []
    exterior_sign = 1 if max(cycles, key=lambda item: abs(item[0]))[0] > 0 else -1
    return [polygon for area, polygon in cycles if (1 if area > 0 else -1) != exterior_sign]


def _match_face(
    warning_polygon: list[tuple[float, float]],
    faces: list[list[tuple[float, float]]],
    assigned: set[int],
) -> int | None:
    point = _polygon_centroid(warning_polygon)
    overlap_scores = [
        (_polygon_overlap_pixels(warning_polygon, face), index)
        for index, face in enumerate(faces)
        if index not in assigned
    ]
    best_overlap, best_index = max(overlap_scores, default=(0, None))
    if best_overlap > 0:
        return best_index
    containing = [
        index
        for index, face in enumerate(faces)
        if index not in assigned and _point_in_polygon(point, face)
    ]
    if containing:
        return min(containing, key=lambda index: abs(_signed_area(faces[index])))
    candidates = [index for index in range(len(faces)) if index not in assigned]
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda index: _squared_distance(point, _polygon_centroid(faces[index])),
    )


def _polygon_overlap_pixels(
    first: list[tuple[float, float]], second: list[tuple[float, float]]
) -> int:
    first_box = _bounds(first)
    second_box = _bounds(second)
    left = max(first_box[0], second_box[0])
    top = max(first_box[1], second_box[1])
    right = min(first_box[2], second_box[2])
    bottom = min(first_box[3], second_box[3])
    if right <= left or bottom <= top:
        return 0
    origin_x = int(left) - 1
    origin_y = int(top) - 1
    width = max(1, int(right) - origin_x + 2)
    height = max(1, int(bottom) - origin_y + 2)
    first_mask = Image.new("1", (width, height))
    second_mask = Image.new("1", (width, height))
    ImageDraw.Draw(first_mask).polygon(
        [(x - origin_x, y - origin_y) for x, y in first], fill=1
    )
    ImageDraw.Draw(second_mask).polygon(
        [(x - origin_x, y - origin_y) for x, y in second], fill=1
    )
    return sum(ImageChops.logical_and(first_mask, second_mask).histogram()[1:])


def _bounds(points: list[tuple[float, float]]) -> tuple[float, float, float, float]:
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return min(xs), min(ys), max(xs), max(ys)


def _signed_area(points: list[tuple[float, float]]) -> float:
    return sum(
        first[0] * second[1] - second[0] * first[1]
        for first, second in zip(points, points[1:])
    ) / 2.0


def _polygon_centroid(points: list[tuple[float, float]]) -> tuple[float, float]:
    usable = points[:-1] if len(points) > 1 and points[0] == points[-1] else points
    return (
        sum(point[0] for point in usable) / len(usable),
        sum(point[1] for point in usable) / len(usable),
    )


def _point_in_polygon(
    point: tuple[float, float], polygon: list[tuple[float, float]]
) -> bool:
    x, y = point
    inside = False
    previous = polygon[-1]
    for current in polygon:
        if (current[1] > y) != (previous[1] > y):
            crossing_x = (previous[0] - current[0]) * (y - current[1]) / (
                previous[1] - current[1]
            ) + current[0]
            if x < crossing_x:
                inside = not inside
        previous = current
    return inside


def _squared_distance(
    first: tuple[float, float], second: tuple[float, float]
) -> float:
    return (first[0] - second[0]) ** 2 + (first[1] - second[1]) ** 2


def _fill_polygons(paths: Iterable[EdgePath]) -> list[list[tuple[float, float]]]:
    by_fill: dict[int, list[list[tuple[float, float]]]] = defaultdict(list)
    for path in paths:
        if path.fill_right and path.fill_right != path.fill_left:
            by_fill[path.fill_right].append(list(path.points))
        if path.fill_left and path.fill_left != path.fill_right:
            by_fill[path.fill_left].append(list(reversed(path.points)))

    polygons: list[list[tuple[float, float]]] = []
    for segments in by_fill.values():
        polygons.extend(_stitch_closed_paths(segments))
    return polygons


def _stitch_closed_paths(
    segments: list[list[tuple[float, float]]],
) -> list[list[tuple[float, float]]]:
    by_start: dict[tuple[float, float], list[int]] = defaultdict(list)
    for index, segment in enumerate(segments):
        by_start[segment[0]].append(index)
    unused = set(range(len(segments)))
    result: list[list[tuple[float, float]]] = []
    while unused:
        index = unused.pop()
        polygon = list(segments[index])
        start = polygon[0]
        while polygon[-1] != start:
            candidates = by_start.get(polygon[-1], [])
            next_index = next((item for item in candidates if item in unused), None)
            if next_index is None:
                break
            unused.remove(next_index)
            polygon.extend(segments[next_index][1:])
        if len(polygon) >= 4 and polygon[-1] == start:
            result.append(polygon)
    return result


def _project(latitude: float, longitude: float) -> tuple[float, float]:
    if longitude < -12.0:
        a, b, c, d, e, f = CANARY_AFFINE
    else:
        a, b, c, d, e, f = MAINLAND_AFFINE
    x = a * longitude + b * latitude + c
    y = d * longitude + e * latitude + f
    if longitude >= -12.0:
        x += _piecewise_linear(
            longitude,
            ((-9.5, 0.0), (-7.69, 0.0), (-4.7, 35.0), (-1.5, 0.0), (4.5, 0.0)),
        )
        y += _piecewise_linear(
            longitude,
            ((-9.5, 0.0), (-7.69, 0.0), (-4.7, 90.0), (-1.5, 55.0), (3.32, 0.0), (4.5, 0.0)),
        )
    if latitude < 36.0 and longitude > -4.0:  # Melilla is nudged upward in the layout.
        y -= 70.0
    return x, y


def _piecewise_linear(value: float, anchors: tuple[tuple[float, float], ...]) -> float:
    for (first_x, first_y), (second_x, second_y) in zip(anchors, anchors[1:]):
        if value <= second_x:
            ratio = (value - first_x) / (second_x - first_x)
            return first_y + ratio * (second_y - first_y)
    return anchors[-1][1]


def _optional_int(value: str | None) -> int | None:
    return int(value) if value else None
