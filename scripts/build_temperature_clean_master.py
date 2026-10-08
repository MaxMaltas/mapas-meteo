from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = (
    ROOT / "temperature_template" / "references" / "MAPA_ALERTAS_ILUSTRATOR.png"
)
DEFAULT_ILLUSTRATOR = ROOT / "MAPA_ALERTAS_ILUSTRATOR.ai"
DEFAULT_GEOMETRY = ROOT / "config" / "alert_zone_faces.illustrator.reference.json"
DEFAULT_OUTPUT = ROOT / "temperature_template" / "assets" / "vector_master"
WIDTH = 1920
HEIGHT = 1080
EXPECTED_SOURCE_SIZE = (1339, 931)
# Tonos medidos en la apariencia PDF del Illustrator de producción tras el
# ajuste editorial del 2026-10-08. La geometría sigue procediendo de la
# exportación limpia ya registrada para no desplazar el mapa térmico.
PROVINCE_COLOUR = (2, 2, 0)
COMMUNITY_COLOUR = (32, 33, 34)
PREVIEW_BACKGROUND = (226, 239, 248, 255)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Separa el PNG cartográfico limpio en capas maestras."
    )
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
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


def pad_l(image: Image.Image, offset: tuple[int, int]) -> Image.Image:
    canvas = Image.new("L", (WIDTH, HEIGHT), 0)
    canvas.paste(image, offset)
    return canvas


def pad_rgba(image: Image.Image, offset: tuple[int, int]) -> Image.Image:
    canvas = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    canvas.alpha_composite(image, offset)
    return canvas


def split_clean_source(source: Image.Image) -> tuple[Image.Image, Image.Image, Image.Image]:
    rgba = source.convert("RGBA")
    alpha = rgba.getchannel("A")
    mask = alpha.point(lambda value: 255 if value >= 128 else 0, mode="L")

    luminance = rgba.convert("L")
    core = Image.new("L", rgba.size, 0)
    core_pixels = core.load()
    source_pixels = rgba.load()
    for y in range(rgba.height):
        for x in range(rgba.width):
            red, green, blue, opacity = source_pixels[x, y]
            if opacity and (red + green + blue) // 3 < 120:
                core_pixels[x, y] = 255
    community_neighbourhood = core.filter(ImageFilter.MaxFilter(5))

    province_alpha = Image.new("L", rgba.size, 0)
    community_alpha = Image.new("L", rgba.size, 0)
    province_pixels = province_alpha.load()
    community_pixels = community_alpha.load()
    neighbourhood_pixels = community_neighbourhood.load()
    luminance_pixels = luminance.load()

    for y in range(rgba.height):
        for x in range(rgba.width):
            opacity = source_pixels[x, y][3]
            if not opacity:
                continue
            strength = 255 - luminance_pixels[x, y]
            if strength < 10:
                continue
            if neighbourhood_pixels[x, y]:
                community_pixels[x, y] = min(opacity, min(255, strength * 2))
            else:
                province_pixels[x, y] = min(opacity, min(255, strength * 6))

    provinces = Image.new("RGBA", rgba.size, (*PROVINCE_COLOUR, 0))
    provinces.putalpha(province_alpha)
    communities = Image.new("RGBA", rgba.size, (*COMMUNITY_COLOUR, 0))
    communities.putalpha(community_alpha)
    return mask, provinces, communities


def white_land(mask: Image.Image) -> Image.Image:
    land = Image.new("RGBA", mask.size, (255, 255, 255, 0))
    land.putalpha(mask)
    return land


def count_nonzero(image: Image.Image) -> int:
    channel = image if image.mode == "L" else image.getchannel("A")
    return sum(1 for value in channel.get_flattened_data() if value)


def main() -> int:
    args = parse_args()
    source_path = args.source.resolve()
    illustrator_path = args.illustrator.resolve()
    geometry_path = args.geometry.resolve()
    output_dir = args.output_dir.resolve()

    for path in (source_path, illustrator_path, geometry_path):
        if not path.exists():
            raise FileNotFoundError(path)

    source = Image.open(source_path).convert("RGBA")
    if source.size != EXPECTED_SOURCE_SIZE:
        raise ValueError(
            f"El PNG limpio mide {source.size}; se esperaba {EXPECTED_SOURCE_SIZE}"
        )
    geometry = json.loads(geometry_path.read_text(encoding="utf-8"))
    if geometry.get("schema_version") != 4:
        raise ValueError("La geometría histórica no tiene el esquema esperado")

    native_mask, native_provinces, native_communities = split_clean_source(source)
    offset = ((WIDTH - source.width) // 2, (HEIGHT - source.height) // 2)
    mask = pad_l(native_mask, offset)
    provinces = pad_rgba(native_provinces, offset)
    communities = pad_rgba(native_communities, offset)
    land = white_land(mask)
    master = Image.alpha_composite(Image.alpha_composite(land, provinces), communities)
    preview = Image.alpha_composite(
        Image.new("RGBA", (WIDTH, HEIGHT), PREVIEW_BACKGROUND), master
    ).convert("RGB")

    if count_nonzero(mask) < 500_000:
        raise ValueError("La superficie terrestre resultante es demasiado pequeña")
    if count_nonzero(provinces) < 7_000:
        raise ValueError("La capa provincial resultante es demasiado pequeña")
    if count_nonzero(communities) < 8_000:
        raise ValueError("La capa autonómica resultante es demasiado pequeña")

    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "mascara_temperatura.png": mask,
        "tierra.png": land,
        "provincias.png": provinces,
        "comunidades.png": communities,
        "mapa_maestro_transparente.png": master,
        "mapa_maestro_preview.png": preview,
    }
    for name, image in outputs.items():
        atomic_save(image, output_dir / name)

    current_ai_hash = sha256(illustrator_path)
    snapshot_ai_hash = geometry["source_sha256"].upper()
    manifest = {
        "phase": "clean_map_master",
        "status": "ready_for_visual_review",
        "created_on": "2026-10-06",
        "size": [WIDTH, HEIGHT],
        "source_clean_png": str(source_path.relative_to(ROOT)).replace("\\", "/"),
        "source_clean_png_sha256": sha256(source_path),
        "source_clean_png_size": list(source.size),
        "placement_offset": list(offset),
        "illustrator_current_sha256": current_ai_hash,
        "geometry_snapshot_source_sha256": snapshot_ai_hash,
        "illustrator_matches_geometry_snapshot": current_ai_hash == snapshot_ai_hash,
        "warning": (
            None
            if current_ai_hash == snapshot_ai_hash
            else "El Illustrator actual no coincide con la geometría validada de producción."
        ),
        "validation": {
            "land_pixels": count_nonzero(mask),
            "province_pixels": count_nonzero(provinces),
            "community_pixels": count_nonzero(communities),
            "land_bbox": list(mask.getbbox()),
            "province_bbox": list(provinces.getchannel("A").getbbox()),
            "community_bbox": list(communities.getchannel("A").getbbox()),
        },
        "outputs": {
            name: {
                "path": str((output_dir / name).relative_to(ROOT)).replace("\\", "/"),
                "mode": image.mode,
                "sha256": sha256(output_dir / name),
            }
            for name, image in outputs.items()
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
    print(json.dumps(manifest["validation"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
