"""Render the fixed Illustrator warning map using its verified zone reference."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw

from meteo_pipeline.alert_map import LEVEL_COLORS, _levels_by_zone

ALERT_ZONE_BORDER = "#C0C0C0"
PROVINCE_BORDER = "#808080"
COMMUNITY_BORDER = "#000000"


def load_reference(reference_path: Path, illustrator_path: Path) -> dict:
    reference = json.loads(reference_path.read_text(encoding="utf-8"))
    if reference.get("schema_version") != 4:
        raise ValueError("La referencia Illustrator no tiene la versión esperada; reconstrúyela")
    digest = hashlib.sha256(illustrator_path.read_bytes()).hexdigest()
    if reference.get("source_sha256") != digest:
        raise ValueError("Illustrator ha cambiado: reconstruye la referencia antes de generar el mapa")
    land = reference.get("land_zones", [])
    marine = reference.get("marine_zones", [])
    land_codes = [zone["code"] for zone in land]
    marine_codes = [zone["code"] for zone in marine]
    if len(land) != 182 or len(marine) != 51 or len(set(land_codes)) != 182 or len(set(marine_codes)) != 51:
        raise ValueError("La referencia no contiene exactamente 182 zonas terrestres y 51 marítimas únicas")
    if any(not zone.get("parts") or not all(part.get("polygons") for part in zone["parts"]) for zone in land):
        raise ValueError("Hay zonas terrestres sin trazado en la referencia")
    if any(not zone.get("polygons") for zone in marine):
        raise ValueError("Hay zonas marítimas sin trazado en la referencia")
    province_outlines = reference.get("province_outlines", [])
    community_outlines = reference.get("community_outlines", [])
    if len(province_outlines) < 50 or len(community_outlines) < 17:
        raise ValueError(
            "Faltan contornos de provincias o comunidades en la referencia: "
            f"provincias={len(province_outlines)}, comunidades={len(community_outlines)}"
        )
    return reference


def render_illustrator_alert_map(
    illustrator_path: Path,
    zone_reference: Path,
    zones: Iterable[dict],
    output_path: Path,
    *,
    width: int = 1920,
    height: int = 1080,
) -> None:
    if (width, height) != (1920, 1080):
        raise ValueError("El mapa Illustrator fijo requiere 1920×1080 píxeles")
    reference = load_reference(zone_reference, illustrator_path)
    levels = _levels_by_zone(zones)
    known = {z["code"] for z in reference["land_zones"] + reference["marine_zones"]}
    unknown = sorted(set(levels) - known)
    if unknown:
        raise ValueError("Zonas AEMET sin dibujo en Illustrator: " + ", ".join(unknown))

    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    marine_outlines = []
    for zone in reference["marine_zones"]:
        level = levels.get(zone["code"], "green")
        if level == "green":
            continue
        for polygon in zone["polygons"]:
            draw.polygon([tuple(point) for point in polygon], fill=LEVEL_COLORS[level])
            marine_outlines.append(polygon)

    land_outlines = []
    for zone in reference["land_zones"]:
        color = LEVEL_COLORS[levels.get(zone["code"], "green")]
        for part in zone["parts"]:
            for polygon in part["polygons"]:
                draw.polygon([tuple(point) for point in polygon], fill=color)
                land_outlines.append(polygon)

    def stroke(polygons: Iterable, colour: str) -> None:
        for polygon in polygons:
            points = [tuple(point) for point in polygon]
            draw.line(points + [points[0]], fill=colour, width=1, joint="curve")

    # Draw broad administrative boundaries last so they win where paths coincide.
    stroke(marine_outlines + land_outlines, ALERT_ZONE_BORDER)
    for outline in reference["province_outlines"]:
        stroke(outline["polygons"], PROVINCE_BORDER)
    for outline in reference["community_outlines"]:
        stroke(outline["polygons"], COMMUNITY_BORDER)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)
