from __future__ import annotations

import argparse
import bisect
import csv
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter

from build_daily_temperature_texture import (
    CANVAS_SIZE,
    atomic_save,
    components,
    exact_component_mask,
    palette_from_legend,
    palette_mask,
    province_centroid_anchors,
    warp_controlled_component,
)


ROOT = Path(__file__).resolve().parents[1]
MASTER_DIR = ROOT / "temperature_template" / "assets" / "vector_master"
DEM_DIR = ROOT / "temperature_template" / "assets" / "dem"
OUTPUT_DIR = ROOT / "temperature_template" / "assets" / "static"
PREVIEW_DIR = ROOT / "temperature_template" / "previews"
VALIDATION_DIR = ROOT / "temperature_template" / "validation"

MAINLAND_FORWARD = (
    2.55671593,
    -0.33588518,
    315.63533646,
    0.14800720,
    2.44004632,
    -81.32952769,
)


@dataclass
class ElevationGrid:
    latitudes: list[float]
    longitudes: list[float]
    values: list[list[float]]

    @classmethod
    def from_csv(cls, path: Path) -> "ElevationGrid":
        latitudes: list[float] = []
        longitudes: list[float] = []
        rows: list[list[float]] = []
        current_latitude: float | None = None
        current_values: list[float] = []
        current_longitudes: list[float] = []
        with path.open("r", encoding="utf-8", newline="") as handle:
            for raw_latitude, raw_longitude, raw_value in csv.reader(handle):
                latitude = float(raw_latitude)
                longitude = float(raw_longitude)
                value = float(raw_value)
                if current_latitude is None or abs(latitude - current_latitude) < 1e-9:
                    current_latitude = latitude
                    current_longitudes.append(longitude)
                    current_values.append(value)
                    continue
                if not longitudes:
                    longitudes = current_longitudes
                elif len(current_longitudes) != len(longitudes):
                    raise ValueError(f"Fila DEM irregular en {path}")
                latitudes.append(current_latitude)
                rows.append(current_values)
                current_latitude = latitude
                current_longitudes = [longitude]
                current_values = [value]
        if current_latitude is not None:
            if not longitudes:
                longitudes = current_longitudes
            elif len(current_longitudes) != len(longitudes):
                raise ValueError(f"Ultima fila DEM irregular en {path}")
            latitudes.append(current_latitude)
            rows.append(current_values)
        if not rows or not longitudes:
            raise ValueError(f"DEM vacio: {path}")
        return cls(latitudes, longitudes, rows)

    def sample(self, latitude: float, longitude: float) -> float:
        latitude = min(max(latitude, self.latitudes[0]), self.latitudes[-1])
        longitude = min(max(longitude, self.longitudes[0]), self.longitudes[-1])
        row0 = max(0, min(len(self.latitudes) - 2, bisect.bisect_right(self.latitudes, latitude) - 1))
        column0 = max(0, min(len(self.longitudes) - 2, bisect.bisect_right(self.longitudes, longitude) - 1))
        row1 = row0 + 1
        column1 = column0 + 1
        latitude0 = self.latitudes[row0]
        latitude1 = self.latitudes[row1]
        longitude0 = self.longitudes[column0]
        longitude1 = self.longitudes[column1]
        fraction_y = (latitude - latitude0) / max(1e-12, latitude1 - latitude0)
        fraction_x = (longitude - longitude0) / max(1e-12, longitude1 - longitude0)
        top = self.values[row0][column0] + (
            self.values[row0][column1] - self.values[row0][column0]
        ) * fraction_x
        bottom = self.values[row1][column0] + (
            self.values[row1][column1] - self.values[row1][column0]
        ) * fraction_x
        return top + (bottom - top) * fraction_y


class SpainElevation:
    def __init__(self, west: ElevationGrid, east: ElevationGrid):
        self.west = west
        self.east = east

    def sample(self, latitude: float, longitude: float) -> float:
        if longitude < 0:
            return self.west.sample(latitude, longitude + 360.0)
        return self.east.sample(latitude, longitude)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Genera un relieve estatico real alineado con el maestro termico."
    )
    parser.add_argument("--date", default="2026-10-06", help="Fecha con PNG AEMET de referencia")
    parser.add_argument("--strength", type=float, default=3.2, help="Exageracion vertical del sombreado")
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def solve_three_by_three(matrix: list[list[float]], values: list[float]) -> list[float]:
    augmented = [row[:] + [value] for row, value in zip(matrix, values)]
    for pivot in range(3):
        best = max(range(pivot, 3), key=lambda row: abs(augmented[row][pivot]))
        augmented[pivot], augmented[best] = augmented[best], augmented[pivot]
        divisor = augmented[pivot][pivot]
        if abs(divisor) < 1e-12:
            raise ValueError("Controles geograficos degenerados")
        augmented[pivot] = [value / divisor for value in augmented[pivot]]
        for row in range(3):
            if row == pivot:
                continue
            factor = augmented[row][pivot]
            augmented[row] = [
                augmented[row][column] - factor * augmented[pivot][column]
                for column in range(4)
            ]
    return [augmented[row][3] for row in range(3)]


def fit_lonlat_affine(
    controls: list[tuple[float, float, float, float]],
) -> tuple[float, float, float, float, float, float]:
    normal = [[0.0] * 3 for _ in range(3)]
    target_x = [0.0] * 3
    target_y = [0.0] * 3
    for longitude, latitude, pixel_x, pixel_y in controls:
        row = [longitude, latitude, 1.0]
        for i in range(3):
            target_x[i] += row[i] * pixel_x
            target_y[i] += row[i] * pixel_y
            for j in range(3):
                normal[i][j] += row[i] * row[j]
    x_coefficients = solve_three_by_three(normal, target_x)
    y_coefficients = solve_three_by_three(normal, target_y)
    return (*x_coefficients, *y_coefficients)


def invert_affine(
    pixel_x: float,
    pixel_y: float,
    affine: tuple[float, float, float, float, float, float],
) -> tuple[float, float]:
    ax, bx, cx, ay, by, cy = affine
    determinant = ax * by - bx * ay
    shifted_x = pixel_x - cx
    shifted_y = pixel_y - cy
    longitude = (by * shifted_x - bx * shifted_y) / determinant
    latitude = (-ay * shifted_x + ax * shifted_y) / determinant
    return longitude, latitude


def smooth(values: list[float], width: int, height: int, passes: int = 1) -> list[float]:
    current = values
    for _ in range(passes):
        horizontal = [0.0] * len(current)
        for y in range(height):
            offset = y * width
            for x in range(width):
                left = current[offset + max(0, x - 1)]
                centre = current[offset + x]
                right = current[offset + min(width - 1, x + 1)]
                horizontal[offset + x] = (left + 2.0 * centre + right) / 4.0
        vertical = [0.0] * len(current)
        for y in range(height):
            above = max(0, y - 1) * width
            centre = y * width
            below = min(height - 1, y + 1) * width
            for x in range(width):
                vertical[centre + x] = (
                    horizontal[above + x]
                    + 2.0 * horizontal[centre + x]
                    + horizontal[below + x]
                ) / 4.0
        current = vertical
    return current


def render_source_hillshade(
    size: tuple[int, int],
    alpha: Image.Image,
    lonlat_affine: tuple[float, float, float, float, float, float],
    elevation: SpainElevation,
    strength: float,
) -> Image.Image:
    width, height = size
    heights = [0.0] * (width * height)
    for y in range(height):
        for x in range(width):
            longitude, latitude = invert_affine(x, y, lonlat_affine)
            heights[y * width + x] = max(0.0, elevation.sample(latitude, longitude))
    heights = smooth(heights, width, height, passes=1)

    centre_longitude, centre_latitude = invert_affine(width / 2, height / 2, lonlat_affine)
    right_longitude, right_latitude = invert_affine(width / 2 + 1, height / 2, lonlat_affine)
    down_longitude, down_latitude = invert_affine(width / 2, height / 2 + 1, lonlat_affine)
    metres_per_degree = 111_320.0
    cosine = math.cos(math.radians(centre_latitude))
    distance_x = metres_per_degree * math.hypot(
        (right_longitude - centre_longitude) * cosine,
        right_latitude - centre_latitude,
    )
    distance_y = metres_per_degree * math.hypot(
        (down_longitude - centre_longitude) * cosine,
        down_latitude - centre_latitude,
    )

    light_x, light_y, light_z = -0.45, -0.45, 0.771362
    shade = bytearray(width * height)
    for y in range(height):
        row = y * width
        above = max(0, y - 1) * width
        below = min(height - 1, y + 1) * width
        for x in range(width):
            left = max(0, x - 1)
            right = min(width - 1, x + 1)
            gradient_x = (
                (heights[row + right] - heights[row + left])
                / max(1.0, 2.0 * distance_x)
                * strength
            )
            gradient_y = (
                (heights[below + x] - heights[above + x])
                / max(1.0, 2.0 * distance_y)
                * strength
            )
            normal_x, normal_y, normal_z = -gradient_x, -gradient_y, 1.0
            magnitude = math.sqrt(
                normal_x * normal_x + normal_y * normal_y + normal_z * normal_z
            )
            illumination = (
                normal_x * light_x + normal_y * light_y + normal_z * light_z
            ) / magnitude
            elevation_lift = min(1.0, heights[row + x] / 3000.0) * 5.0
            value = round(128.0 + (illumination - light_z) * 310.0 + elevation_lift)
            shade[row + x] = max(58, min(198, value))

    result = Image.frombytes("L", size, bytes(shade)).convert("RGBA")
    result.putalpha(alpha)
    return result


def soft_light_preview(base: Image.Image, relief: Image.Image, opacity: float) -> Image.Image:
    background = base.convert("RGBA")
    base_pixels = list(background.get_flattened_data())
    relief_pixels = list(relief.convert("RGBA").get_flattened_data())
    output = []
    for base_colour, relief_colour in zip(base_pixels, relief_pixels):
        if not relief_colour[3]:
            output.append(base_colour)
            continue
        blend = relief_colour[0] / 255.0
        alpha = opacity * relief_colour[3] / 255.0
        channels = []
        for channel in base_colour[:3]:
            value = channel / 255.0
            if blend <= 0.5:
                mixed = value - (1.0 - 2.0 * blend) * value * (1.0 - value)
            else:
                detail = (
                    ((16.0 * value - 12.0) * value + 4.0) * value
                    if value <= 0.25
                    else math.sqrt(value)
                )
                mixed = value + (2.0 * blend - 1.0) * (detail - value)
            channels.append(round((value + (mixed - value) * alpha) * 255.0))
        output.append((*channels, base_colour[3]))
    result = Image.new("RGBA", background.size)
    result.putdata(output)
    return result


def main() -> int:
    args = parse_args()
    west_path = DEM_DIR / "etopo_60s_stride2_west.csv"
    east_path = DEM_DIR / "etopo_60s_stride2_east.csv"
    raw_dir = ROOT / "data" / "raw" / args.date
    peninsula_path = raw_dir / "temperaturas_maximas.png"
    mask_path = MASTER_DIR / "mascara_temperatura.png"
    provinces_path = MASTER_DIR / "provincias.png"
    communities_path = MASTER_DIR / "comunidades.png"
    required = [
        west_path,
        east_path,
        peninsula_path,
        mask_path,
        provinces_path,
        communities_path,
    ]
    for path in required:
        if not path.exists() or path.stat().st_size == 0:
            raise FileNotFoundError(path)

    elevation = SpainElevation(
        ElevationGrid.from_csv(west_path),
        ElevationGrid.from_csv(east_path),
    )
    peninsula = Image.open(peninsula_path).convert("RGB")
    pen_valid = palette_mask(peninsula, palette_from_legend(peninsula, 590, 8, 476))
    pen_alpha = pen_valid.filter(ImageFilter.MaxFilter(5))

    peninsula_lonlat = fit_lonlat_affine(
        [
            (-9.2710, 42.8820, 73.0, 108.0),
            (3.3170, 42.3190, 500.0, 128.0),
            (-5.6100, 36.0000, 188.0, 431.0),
        ]
    )
    source_peninsula_relief = render_source_hillshade(
        peninsula.size,
        pen_alpha,
        peninsula_lonlat,
        elevation,
        args.strength,
    )

    land_mask = Image.open(mask_path).convert("L")
    provinces = Image.open(provinces_path).convert("RGBA")
    communities = Image.open(communities_path).convert("RGBA")
    target_components = components(land_mask)
    mainland = target_components[0]
    mainland_mask = exact_component_mask(land_mask, mainland)
    anchors, metrics = province_centroid_anchors(
        pen_valid,
        land_mask,
        mainland_mask,
        provinces,
        communities,
        MAINLAND_FORWARD,
    )
    anchors.extend(
        [
            ("cabo_fisterra", (73, 108), (466, 193)),
            ("cabo_de_creus", (500, 128), (1551, 305)),
            ("punta_de_tarifa", (188, 431), (710, 1004)),
        ]
    )
    relief = warp_controlled_component(
        source_peninsula_relief,
        mainland_mask,
        MAINLAND_FORWARD,
        anchors,
        search_radius=3,
        control_grid_step=8,
    )

    # El relieve es deliberadamente peninsular. Baleares y Canarias conservan la
    # textura termica diaria, pero no reciben sombreado topografico porque su
    # colocacion en el grafico es editorial y exige escalados independientes.
    relief.putalpha(mainland_mask)
    output_path = OUTPUT_DIR / "relieve_dem.png"
    atomic_save(relief, output_path)

    daily_temperature = (
        ROOT
        / "temperature_template"
        / "assets"
        / "daily"
        / args.date
        / "temperatura_rellenada.png"
    )
    if daily_temperature.exists():
        base = Image.alpha_composite(
            Image.new("RGBA", CANVAS_SIZE, (226, 239, 248, 255)),
            Image.open(daily_temperature).convert("RGBA"),
        )
    else:
        base = Image.new("RGBA", CANVAS_SIZE, (226, 239, 248, 255))
        base.alpha_composite(Image.open(MASTER_DIR / "tierra.png").convert("RGBA"))
    preview = soft_light_preview(base, relief, opacity=0.28)
    preview = Image.alpha_composite(Image.alpha_composite(preview, provinces), communities)
    preview_path = PREVIEW_DIR / "relieve_dem_preview.png"
    atomic_save(preview.convert("RGB"), preview_path)

    manifest = {
        "phase": "static_real_dem_relief",
        "status": "generated_mainland_only_pending_after_effects_reload",
        "date": args.date,
        "source": {
            "dataset": "NOAA NCEI ETOPO 2022 surface elevation",
            "resolution": "60 arc-second sampled with stride 2",
            "west_csv_sha256": sha256(west_path),
            "east_csv_sha256": sha256(east_path),
        },
        "canvas_size": list(CANVAS_SIZE),
        "hillshade": {
            "light_direction": "northwest",
            "strength": args.strength,
            "neutral_gray": 128,
            "preview_soft_light_opacity": 28,
        },
        "registration": {
            "mainland_control_points": len(anchors),
            "province_metrics": metrics,
            "scope": "mainland_only",
            "balearic_islands": 0,
            "canary_islands": 0,
        },
        "outputs": {
            str(output_path.relative_to(ROOT)).replace("\\", "/"): sha256(output_path),
            str(preview_path.relative_to(ROOT)).replace("\\", "/"): sha256(preview_path),
        },
        "after_effects": {
            "project_modified_by_this_run": False,
            "linked_footage_path_unchanged": True,
            "manual_user_adjustments_preserved": True,
            "action_if_project_is_open": "reload_relieve_dem_footage",
        },
    }
    manifest_path = VALIDATION_DIR / "phase5_relief_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(output_path)
    print(preview_path)
    print(manifest_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
