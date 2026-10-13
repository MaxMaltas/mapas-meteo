from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
MASTER_DIR = ROOT / "temperature_template" / "assets" / "vector_master"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Combina la textura termica diaria con limites provinciales que no "
            "coinciden con costas ni limites autonomicos."
        )
    )
    parser.add_argument("--date", required=True, help="Fecha ISO, por ejemplo 2026-10-09")
    parser.add_argument(
        "--clearance",
        type=int,
        default=2,
        help="Separacion en pixeles alrededor de costas y limites autonomicos.",
    )
    return parser.parse_args()


def count_nonzero(channel: Image.Image) -> int:
    return sum(1 for value in channel.get_flattened_data() if value)


def atomic_save(image: Image.Image, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.stem + ".writing.png")
    image.save(temporary, format="PNG", optimize=True)
    temporary.replace(destination)


def main() -> int:
    args = parse_args()
    if args.clearance < 0:
        raise ValueError("clearance no puede ser negativo")

    daily_dir = ROOT / "temperature_template" / "assets" / "daily" / args.date
    temperature_path = daily_dir / "temperatura_rellenada.png"
    provinces_path = MASTER_DIR / "provincias.png"
    communities_path = MASTER_DIR / "comunidades.png"
    required = (temperature_path, provinces_path, communities_path)
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError("Faltan archivos obligatorios: " + ", ".join(missing))

    temperature = Image.open(temperature_path).convert("RGBA")
    provinces = Image.open(provinces_path).convert("RGBA")
    communities = Image.open(communities_path).convert("RGBA")
    if not (temperature.size == provinces.size == communities.size):
        raise ValueError("Las capas termica, provincial y autonomica no tienen el mismo tamano")

    province_alpha = provinces.getchannel("A")
    community_alpha = communities.getchannel("A")
    if args.clearance:
        filter_size = args.clearance * 2 + 1
        community_exclusion = community_alpha.filter(ImageFilter.MaxFilter(filter_size))
    else:
        community_exclusion = community_alpha

    deduplicated_alpha = ImageChops.subtract(province_alpha, community_exclusion)
    deduplicated_provinces = provinces.copy()
    deduplicated_provinces.putalpha(deduplicated_alpha)
    combined = Image.alpha_composite(temperature, deduplicated_provinces)

    overlay_path = daily_dir / "temperatura_limites_sin_duplicados.png"
    province_path = daily_dir / "provincias_sin_duplicados.png"
    report_path = daily_dir / "limites_sin_duplicados.json"
    atomic_save(combined, overlay_path)
    atomic_save(deduplicated_provinces, province_path)

    original_pixels = count_nonzero(province_alpha)
    retained_pixels = count_nonzero(deduplicated_alpha)
    report = {
        "date": args.date,
        "clearance_pixels": args.clearance,
        "province_pixels_original": original_pixels,
        "province_pixels_retained": retained_pixels,
        "province_pixels_removed": original_pixels - retained_pixels,
        "method": "province_alpha_minus_dilated_community_and_coast_alpha",
        "temperature_source": str(temperature_path.relative_to(ROOT)).replace("\\", "/"),
        "province_source": str(provinces_path.relative_to(ROOT)).replace("\\", "/"),
        "community_source": str(communities_path.relative_to(ROOT)).replace("\\", "/"),
        "output": str(overlay_path.relative_to(ROOT)).replace("\\", "/"),
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
