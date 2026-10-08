from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageChops, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ILLUSTRATOR = ROOT / "MAPA_ALERTAS_ILUSTRATOR.ai"
DEFAULT_GEOMETRY = ROOT / "config" / "alert_zone_faces.illustrator.reference.json"
DEFAULT_OUTPUT = ROOT / "temperature_template" / "assets" / "vector_master"
WIDTH = 1920
HEIGHT = 1080
SUPERSAMPLE = 4
PROVINCE_COLOUR = (190, 190, 190, 255)
COMMUNITY_COLOUR = (32, 32, 32, 255)
PREVIEW_BACKGROUND = (226, 239, 248, 255)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Genera las capas maestras del mapa térmico desde Illustrator."
    )
    parser.add_argument("--illustrator", type=Path, default=DEFAULT_ILLUSTRATOR)
    parser.add_argument("--geometry", type=Path, default=DEFAULT_GEOMETRY)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def atomic_save(image: Image.Image, destination: Path) -> None:
    temporary = destination.with_name(destination.stem + ".writing.png")
    image.save(temporary, format="PNG", optimize=True)
    temporary.replace(destination)


def land_polygons(reference: dict) -> Iterable[list[tuple[float, float]]]:
    for zone in reference["land_zones"]:
        for part in zone["parts"]:
            for polygon in part["polygons"]:
                yield [tuple(point) for point in polygon]


def render_land_mask(reference: dict) -> Image.Image:
    mask = Image.new("L", (WIDTH, HEIGHT), 0)
    draw = ImageDraw.Draw(mask)
    for polygon in land_polygons(reference):
        draw.polygon(polygon, fill=255)
    return mask


def render_outline_layer(
    outlines: Iterable[dict],
    colour: tuple[int, int, int, int],
    width: float,
) -> Image.Image:
    scale = SUPERSAMPLE
    canvas = Image.new("RGBA", (WIDTH * scale, HEIGHT * scale), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    for outline in outlines:
        for polygon in outline["polygons"]:
            points = [
                (round(point[0] * scale), round(point[1] * scale))
                for point in polygon
            ]
            if len(points) < 2:
                continue
            draw.line(
                points + [points[0]],
                fill=colour,
                width=max(1, round(width * scale)),
                joint="curve",
            )
    return canvas.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)


def white_land(mask: Image.Image) -> Image.Image:
    land = Image.new("RGBA", mask.size, (255, 255, 255, 0))
    land.putalpha(mask)
    return land


def land_mask_from_closed_outlines(*outline_layers: Image.Image) -> Image.Image:
    alpha = Image.new("L", (WIDTH, HEIGHT), 0)
    for layer in outline_layers:
        alpha = ImageChops.lighter(alpha, layer.getchannel("A"))
    barrier = alpha.point(lambda value: 255 if value >= 16 else 0, mode="L")
    barrier = barrier.filter(ImageFilter.MaxFilter(3))
    enclosed = ImageChops.invert(barrier)
    ImageDraw.floodfill(enclosed, (0, 0), 0, thresh=0)
    return ImageChops.lighter(barrier, enclosed)


def transparent_master(
    land: Image.Image,
    provinces: Image.Image,
    communities: Image.Image,
) -> Image.Image:
    return Image.alpha_composite(
        Image.alpha_composite(land, provinces), communities
    )


def preview(master: Image.Image) -> Image.Image:
    background = Image.new("RGBA", master.size, PREVIEW_BACKGROUND)
    return Image.alpha_composite(background, master).convert("RGB")


def alpha_pixel_count(image: Image.Image) -> int:
    if image.mode == "L":
        return sum(1 for value in image.get_flattened_data() if value)
    alpha = image.getchannel("A")
    return sum(1 for value in alpha.get_flattened_data() if value)


def validate_geometry(
    mask: Image.Image,
    provinces: Image.Image,
    communities: Image.Image,
) -> dict:
    if mask.getextrema() != (0, 255):
        raise ValueError("La máscara terrestre no es binaria")
    if not mask.getbbox():
        raise ValueError("La máscara terrestre está vacía")
    if not provinces.getchannel("A").getbbox():
        raise ValueError("La capa provincial está vacía")
    if not communities.getchannel("A").getbbox():
        raise ValueError("La capa autonómica está vacía")

    land_pixels = alpha_pixel_count(mask)
    province_pixels = alpha_pixel_count(provinces)
    community_pixels = alpha_pixel_count(communities)
    if land_pixels < 250_000:
        raise ValueError(f"Superficie terrestre inesperadamente pequeña: {land_pixels}")
    if province_pixels < 10_000 or community_pixels < 10_000:
        raise ValueError("Alguna capa de límites contiene muy pocos píxeles")

    return {
        "land_pixels": land_pixels,
        "province_outline_pixels": province_pixels,
        "community_outline_pixels": community_pixels,
        "land_bbox": list(mask.getbbox()),
        "province_bbox": list(provinces.getchannel("A").getbbox()),
        "community_bbox": list(communities.getchannel("A").getbbox()),
    }


def main() -> int:
    args = parse_args()
    illustrator_path = args.illustrator.resolve()
    geometry_path = args.geometry.resolve()
    output_dir = args.output_dir.resolve()

    if not illustrator_path.exists():
        raise FileNotFoundError(f"No existe el Illustrator: {illustrator_path}")
    if not geometry_path.exists():
        raise FileNotFoundError(f"No existe la geometría validada: {geometry_path}")
    reference = json.loads(geometry_path.read_text(encoding="utf-8"))
    if reference.get("schema_version") != 4:
        raise ValueError("La instantánea geométrica no tiene el esquema 4")
    if len(reference.get("land_zones", [])) != 182:
        raise ValueError("La instantánea no contiene 182 zonas terrestres")
    if len(reference.get("marine_zones", [])) != 51:
        raise ValueError("La instantánea no contiene 51 zonas marítimas")
    if len(reference.get("province_outlines", [])) != 66:
        raise ValueError("La instantánea no contiene 66 contornos provinciales")
    if len(reference.get("community_outlines", [])) != 31:
        raise ValueError("La instantánea no contiene 31 contornos autonómicos")
    output_dir.mkdir(parents=True, exist_ok=True)

    provinces = render_outline_layer(
        reference["province_outlines"], PROVINCE_COLOUR, width=1.1
    )
    communities = render_outline_layer(
        reference["community_outlines"], COMMUNITY_COLOUR, width=2.0
    )
    mask = render_land_mask(reference)
    land = white_land(mask)
    master = transparent_master(land, provinces, communities)
    master_preview = preview(master)

    images = {
        "mascara_temperatura.png": mask,
        "tierra.png": land,
        "provincias.png": provinces,
        "comunidades.png": communities,
        "mapa_maestro_transparente.png": master,
        "mapa_maestro_preview.png": master_preview,
    }
    for name, image in images.items():
        atomic_save(image, output_dir / name)

    validation = validate_geometry(mask, provinces, communities)
    manifest = {
        "phase": "vector_master",
        "status": "ready_for_visual_review",
        "created_on": "2026-10-06",
        "size": [WIDTH, HEIGHT],
        "illustrator": str(illustrator_path.relative_to(ROOT)).replace("\\", "/"),
        "illustrator_current_sha256": sha256(illustrator_path),
        "geometry_snapshot": str(geometry_path.relative_to(ROOT)).replace("\\", "/"),
        "geometry_snapshot_sha256": sha256(geometry_path),
        "geometry_snapshot_source_sha256": reference["source_sha256"].upper(),
        "illustrator_matches_geometry_snapshot": (
            sha256(illustrator_path) == reference["source_sha256"].upper()
        ),
        "source_counts": {
            "land_zones": len(reference["land_zones"]),
            "land_parts": sum(len(zone["parts"]) for zone in reference["land_zones"]),
            "marine_zones_excluded": len(reference["marine_zones"]),
            "province_outlines": len(reference["province_outlines"]),
            "community_outlines": len(reference["community_outlines"]),
        },
        "land_mask_source": "validated terrestrial polygons from geometry snapshot",
        "styles": {
            "province_colour": "#BEBEBE",
            "province_width_px": 1.1,
            "community_colour": "#202020",
            "community_width_px": 2.0,
        },
        "validation": validation,
        "outputs": {
            name: {
                "path": str((output_dir / name).relative_to(ROOT)).replace("\\", "/"),
                "mode": image.mode,
                "sha256": sha256(output_dir / name),
            }
            for name, image in images.items()
        },
    }
    manifest_path = output_dir.parent.parent / "validation" / "vector_master_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_manifest = manifest_path.with_suffix(".writing.json")
    temporary_manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporary_manifest.replace(manifest_path)

    print(output_dir)
    print(manifest_path)
    print(json.dumps(validation, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
