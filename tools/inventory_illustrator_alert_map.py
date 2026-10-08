"""Inventory Illustrator objects without guessing their AEMET identities.

Legacy form inventory. The production mapping is built by
build_illustrator_zone_reference.py from Illustrator object names.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from meteo_pipeline.illustrator_map import illustrator_sha256, read_illustrator_shapes
from tools.build_alert_zone_face_reference import _read_cap_snapshots


# These are visually distinguishable island forms. They are candidate links,
# not approved production assignments; every shape still needs final review.
ISLAND_CANDIDATES = {
    "Fm225": "645401",  # Sierra Tramontana
    "Fm226": "645402",  # Norte y nordeste de Mallorca
    "Fm227": "645403",  # Interior de Mallorca
    "Fm228": "645404",  # Sur de Mallorca
    "Fm229": "645405",  # Levante mallorquín
    "Fm230": "645501",  # Menorca
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "MAPA_ALERTAS_ILUSTRATOR.ai")
    parser.add_argument("--cap", type=Path, default=ROOT / "data/raw/2026-10-01/avisos_cap.data.tar")
    parser.add_argument(
        "--reference", type=Path,
        default=ROOT / "output/illustrator_zone_inventory.json",
    )
    parser.add_argument(
        "--atlas", type=Path, default=ROOT / "output/illustrator_zone_inventory.png"
    )
    args = parser.parse_args()
    shapes = read_illustrator_shapes(args.source)
    land = [shape for shape in shapes if shape.layer == "ZONAS AEMET" and shape.bounds[0] < 1700]
    marine = [shape for shape in shapes if shape.layer == "MAR"]
    snapshots = _read_cap_snapshots(args.cap)
    selected = max(snapshots.items(), key=lambda item: len(item[1]))
    sent, catalog = selected
    if len(catalog) != 233:
        raise ValueError(f"La instantánea CAP solo contiene {len(catalog)} de 233 zonas")
    audit_path = ROOT / "config/illustrator_split_zone_audit.json"
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    digest = illustrator_sha256(args.source)
    if audit["source_ai_sha256"] != digest:
        raise ValueError("La auditoría de zonas divididas no corresponde a este .ai")
    matched = {}
    available = {shape.form_id for shape in land + marine}
    for group in audit["matched_split_zones"]:
        code = group["zone_code"]
        if code not in catalog or len(catalog[code]["polygons"]) != 2:
            raise ValueError(f"{code} no tiene dos polígonos en CAP")
        for form_id in group["form_ids"]:
            if form_id not in available or form_id in matched:
                raise ValueError(f"Forma inexistente o repetida: {form_id}")
            matched[form_id] = code
    document = {
        "schema_version": 2,
        "status": "inventory_unverified_not_for_daily_rendering",
        "source": str(args.source.relative_to(ROOT)).replace("\\", "/"),
        "source_sha256": digest,
        "source_cap": str(args.cap.relative_to(ROOT)).replace("\\", "/"),
        "source_cap_snapshot": sent,
        "layer_counts": dict(Counter(shape.layer for shape in shapes)),
        "land_shape_count": len(land),
        "marine_shape_count": len(marine),
        "aemet_land_code_count": sum(not code.endswith("C") for code in catalog),
        "aemet_marine_code_count": sum(code.endswith("C") for code in catalog),
        "matched_split_zone_count": len(audit["matched_split_zones"]),
        "split_zone_conflicts": audit["conflicts"],
        "shapes": [
            {
                "form_id": shape.form_id,
                "layer": shape.layer,
                "bounds": [round(value, 3) for value in shape.bounds],
                "area_px2": round(shape.area, 3),
                "zone_code": matched.get(shape.form_id, ISLAND_CANDIDATES.get(shape.form_id)),
                "review_status": (
                    "geometry_matched" if shape.form_id in matched
                    else "candidate_needs_review" if shape.form_id in ISLAND_CANDIDATES
                    else "unidentified"
                ),
            }
            for shape in land + marine
        ],
        "aemet_zone_catalog": [
            {"zone_code": code, "zone_name": catalog[code]["name"]}
            for code in sorted(catalog)
        ],
    }
    args.reference.parent.mkdir(parents=True, exist_ok=True)
    args.reference.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _render_atlas(shapes, args.atlas)
    print(f"{len(land)} formas terrestres, {len(marine)} marítimas, {len(catalog)} códigos AEMET")
    print(args.reference)
    print(args.atlas)


def _render_atlas(shapes, destination: Path) -> None:
    image = Image.new("RGB", (1920, 1080), "white")
    draw = ImageDraw.Draw(image)
    fills = {"ZONAS AEMET": "#d7edc9", "MAR": "#e7f4fd"}
    outlines = {"ZONAS AEMET": "#64855b", "MAR": "#3595cb", "PROVINCIAS": "#333333", "CCAA": "#888888"}
    for shape in shapes:
        if shape.layer == "ZONAS AEMET" and shape.bounds[0] >= 1700:
            continue  # Illustrator's four colour-key rectangles, not warning zones.
        for polygon in shape.polygons:
            if shape.layer in fills:
                draw.polygon(polygon, fill=fills[shape.layer], outline=outlines[shape.layer])
            else:
                draw.line(list(polygon) + [polygon[0]], fill=outlines[shape.layer], width=1)
    font = ImageFont.truetype("arial.ttf", 12)
    for shape in shapes:
        if shape.layer not in ("ZONAS AEMET", "MAR") or shape.bounds[0] >= 1700:
            continue
        if shape.area < 80:
            continue
        left, top, right, bottom = shape.bounds
        x, y = (left + right) / 2, (top + bottom) / 2
        label = shape.form_id[2:]
        colour = "#1e4a19" if shape.layer == "ZONAS AEMET" else "#05638e"
        draw.text((x, y), label, fill=colour, font=font, anchor="mm", stroke_width=2, stroke_fill="white")
    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination)


if __name__ == "__main__":
    main()
