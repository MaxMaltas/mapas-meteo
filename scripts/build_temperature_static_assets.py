from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from collections import deque
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE = ROOT / "(Material de archivo)" / "bg" / "TEMPERATURAS.png"
DEFAULT_REFERENCE = (
    ROOT / "data" / "generated" / "2026-10-06" / "temperaturas_final.png"
)
DEFAULT_OUTPUT = ROOT / "temperature_template" / "assets" / "static"
EXPECTED_SIZE = (1672, 941)
DIFFERENCE_THRESHOLD = 24


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Genera los activos estáticos iniciales de la plantilla térmica."
    )
    parser.add_argument("--base", type=Path, default=DEFAULT_BASE)
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def maximum_rgb_difference(left: Image.Image, right: Image.Image) -> Image.Image:
    difference = ImageChops.difference(left, right)
    red, green, blue = difference.split()
    return ImageChops.lighter(ImageChops.lighter(red, green), blue)


def geographic_roi(size: tuple[int, int]) -> Image.Image:
    roi = Image.new("L", size, 0)
    draw = ImageDraw.Draw(roi)
    # Península, Baleares, Ceuta/Melilla y el volumen inmediato del mapa.
    draw.rectangle((420, 260, 1450, 890), fill=255)
    # Canarias, dispuestas de forma estilizada en la esquina inferior izquierda.
    draw.rectangle((130, 690, 540, 920), fill=255)
    return roi


def retain_components(
    mask: Image.Image,
    minimum_area: int = 24,
    geographic_filter: bool = False,
    border_filter: bool = False,
) -> Image.Image:
    width, height = mask.size
    source = bytearray(mask.tobytes())
    visited = bytearray(width * height)
    output = bytearray(width * height)

    for start, value in enumerate(source):
        if value == 0 or visited[start]:
            continue
        queue: deque[int] = deque([start])
        visited[start] = 1
        component: list[int] = []
        sum_x = 0
        sum_y = 0
        while queue:
            index = queue.popleft()
            component.append(index)
            x = index % width
            y = index // width
            sum_x += x
            sum_y += y
            if x > 0:
                neighbour = index - 1
                if source[neighbour] and not visited[neighbour]:
                    visited[neighbour] = 1
                    queue.append(neighbour)
            if x + 1 < width:
                neighbour = index + 1
                if source[neighbour] and not visited[neighbour]:
                    visited[neighbour] = 1
                    queue.append(neighbour)
            if y > 0:
                neighbour = index - width
                if source[neighbour] and not visited[neighbour]:
                    visited[neighbour] = 1
                    queue.append(neighbour)
            if y + 1 < height:
                neighbour = index + width
                if source[neighbour] and not visited[neighbour]:
                    visited[neighbour] = 1
                    queue.append(neighbour)
        centre_x = sum_x / len(component)
        centre_y = sum_y / len(component)
        allowed_location = True
        if geographic_filter:
            allowed_location = (
                len(component) >= 1000
                or (420 <= centre_x <= 1210 and 260 <= centre_y <= 850)
                or (1160 <= centre_x <= 1450 and 430 <= centre_y <= 700)
                or (120 <= centre_x <= 550 and 680 <= centre_y <= 930)
                or (550 <= centre_x <= 1000 and 760 <= centre_y <= 930)
            )
        if border_filter:
            allowed_location = (
                len(component) >= 1000
                or (120 <= centre_x <= 550 and 680 <= centre_y <= 930)
                or (1160 <= centre_x <= 1450 and 430 <= centre_y <= 700)
                or (550 <= centre_x <= 1000 and 780 <= centre_y <= 930)
            )
        if len(component) >= minimum_area and allowed_location:
            for index in component:
                output[index] = 255

    return Image.frombytes("L", (width, height), bytes(output))


def fill_holes(mask: Image.Image) -> Image.Image:
    inverse = ImageChops.invert(mask)
    ImageDraw.floodfill(inverse, (0, 0), 0, thresh=0)
    return ImageChops.lighter(mask, inverse)


def build_surface_mask(base: Image.Image, reference: Image.Image) -> tuple[Image.Image, Image.Image]:
    difference = maximum_rgb_difference(base, reference)
    binary = difference.point(
        lambda value: 255 if value >= DIFFERENCE_THRESHOLD else 0,
        mode="L",
    )
    binary = ImageChops.multiply(binary, geographic_roi(base.size))
    # Cierra líneas finas y pequeños huecos sin cambiar la posición global.
    closed = binary.filter(ImageFilter.MaxFilter(7)).filter(ImageFilter.MinFilter(7))
    components = retain_components(closed)
    filled = fill_holes(components)
    # Una erosión mínima protege el núcleo brillante de las costas.
    surface = filled.filter(ImageFilter.MinFilter(3))
    surface = retain_components(surface, geographic_filter=True)
    return surface, difference


def rgba_from_alpha(source: Image.Image, alpha: Image.Image) -> Image.Image:
    rgba = source.convert("RGBA")
    rgba.putalpha(alpha)
    return rgba


def build_border_mask(
    base: Image.Image,
    surface: Image.Image,
    difference: Image.Image,
) -> Image.Image:
    outer = ImageChops.difference(
        surface.filter(ImageFilter.MaxFilter(13)),
        surface.filter(ImageFilter.MinFilter(9)),
    )
    edge = base.convert("L").filter(ImageFilter.FIND_EDGES)
    rgb = base.load()
    edge_pixels = edge.load()
    difference_pixels = difference.load()
    surface_pixels = surface.load()
    unchanged_edge_seed = Image.new("L", base.size, 0)
    seed_pixels = unchanged_edge_seed.load()

    for y in range(base.height):
        for x in range(base.width):
            if not surface_pixels[x, y] or edge_pixels[x, y] < 28:
                continue
            # Los límites fijos apenas cambian entre la base y la referencia.
            # La textura de la cara superior sí cambia al recibir el campo térmico.
            red, green, blue = rgb[x, y]
            spread = max(red, green, blue) - min(red, green, blue)
            luminance = (red + green + blue) // 3
            fixed_edge = difference_pixels[x, y] <= 52
            cyan_edge = (
                edge_pixels[x, y] >= 32
                and blue >= 100
                and blue - red >= 30
                and green - red >= 8
                and spread >= 35
            )
            dark_cyan_core = (
                edge_pixels[x, y] >= 36
                and max(red, green, blue) <= 105
                and blue - red >= 18
            )
            strong_line_profile = (
                luminance <= 85 or luminance >= 195 or spread >= 90
            )
            if strong_line_profile and (fixed_edge or cyan_edge or dark_cyan_core):
                seed_pixels[x, y] = 255

    internal = unchanged_edge_seed.filter(ImageFilter.MaxFilter(5))
    internal = retain_components(internal, minimum_area=30)
    map_neighbourhood = surface.filter(ImageFilter.MaxFilter(17))
    combined = ImageChops.multiply(
        ImageChops.lighter(outer, internal), map_neighbourhood
    )
    return retain_components(combined, minimum_area=30, border_filter=True)


def build_side_mask(surface: Image.Image) -> Image.Image:
    broad = surface.filter(ImageFilter.MaxFilter(61))
    shifted = Image.new("L", surface.size, 0)
    shifted.paste(surface.filter(ImageFilter.MaxFilter(31)), (0, 48))
    volume = ImageChops.lighter(broad, shifted)
    return ImageChops.subtract(volume, surface)


def build_relief(base: Image.Image, surface: Image.Image) -> Image.Image:
    luminance = base.convert("L").filter(ImageFilter.GaussianBlur(2.0))
    return Image.merge("RGBA", (luminance, luminance, luminance, surface))


def build_preview(
    base: Image.Image, surface: Image.Image, borders: Image.Image
) -> Image.Image:
    preview = base.convert("RGBA")
    red = Image.new("RGBA", base.size, (255, 32, 32, 0))
    red.putalpha(surface.point(lambda value: 92 if value else 0))
    preview = Image.alpha_composite(preview, red)
    green = Image.new("RGBA", base.size, (0, 255, 110, 0))
    green.putalpha(borders.point(lambda value: 220 if value else 0))
    return Image.alpha_composite(preview, green).convert("RGB")


def build_flat_colour_test(
    base: Image.Image,
    surface: Image.Image,
    border_overlay: Image.Image,
) -> Image.Image:
    test = base.convert("RGBA")
    colour = Image.new("RGBA", base.size, (255, 180, 0, 0))
    colour.putalpha(surface)
    test = Image.alpha_composite(test, colour)
    return Image.alpha_composite(test, border_overlay).convert("RGB")


def main() -> int:
    args = parse_args()
    base_path = args.base.resolve()
    reference_path = args.reference.resolve()
    output_dir = args.output_dir.resolve()

    if not base_path.exists():
        raise FileNotFoundError(f"No existe la base: {base_path}")
    if not reference_path.exists():
        raise FileNotFoundError(f"No existe la referencia: {reference_path}")

    base = Image.open(base_path).convert("RGB")
    reference = Image.open(reference_path).convert("RGB")
    if base.size != EXPECTED_SIZE or reference.size != EXPECTED_SIZE:
        raise ValueError(
            f"Tamaño inesperado: base={base.size}, referencia={reference.size}, "
            f"esperado={EXPECTED_SIZE}"
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    surface, difference = build_surface_mask(base, reference)
    borders = build_border_mask(base, surface, difference)
    sides = build_side_mask(surface)
    border_overlay = rgba_from_alpha(base, borders)

    outputs = {
        "fondo_titulo.png": None,
        "mascara_superficie.png": surface,
        "superficie_original.png": rgba_from_alpha(base, surface),
        "bordes_brillos.png": border_overlay,
        "laterales_sombras.png": rgba_from_alpha(base, sides),
        "relieve.png": build_relief(base, surface),
        "diferencia_referencia.png": difference,
        "separacion_preview.png": build_preview(base, surface, borders),
        "prueba_color_plano.png": build_flat_colour_test(
            base, surface, border_overlay
        ),
    }

    for name, image in outputs.items():
        destination = output_dir / name
        temporary = destination.with_name(destination.stem + ".writing.png")
        if image is None:
            shutil.copy2(base_path, temporary)
        else:
            image.save(temporary, format="PNG", optimize=True)
        temporary.replace(destination)

    surface_pixels = sum(1 for value in surface.get_flattened_data() if value)
    border_pixels = sum(1 for value in borders.get_flattened_data() if value)
    side_pixels = sum(1 for value in sides.get_flattened_data() if value)
    manifest = {
        "phase": 2,
        "status": "complete",
        "base": str(base_path),
        "base_sha256": sha256(base_path),
        "reference_used_for_segmentation": str(reference_path),
        "reference_role": "localizar las caras superiores; no aporta píxeles a los activos",
        "size": list(EXPECTED_SIZE),
        "difference_threshold": DIFFERENCE_THRESHOLD,
        "pixel_counts": {
            "surface": surface_pixels,
            "borders": border_pixels,
            "sides_region": side_pixels,
        },
        "outputs": {
            name: {
                "path": str((output_dir / name).relative_to(ROOT)).replace("\\", "/"),
                "sha256": sha256(output_dir / name),
            }
            for name in outputs
        },
        "review_required": [
            "contorno de Galicia y costa cantábrica",
            "Pirineos y frontera con Francia",
            "costa mediterránea y Andalucía",
            "Baleares",
            "Canarias",
            "Ceuta y Melilla",
            "líneas internas detectadas como bordes cian",
        ],
    }
    manifest_path = output_dir.parent.parent / "validation" / "phase2_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(output_dir)
    print(manifest_path)
    print(json.dumps(manifest["pixel_counts"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
