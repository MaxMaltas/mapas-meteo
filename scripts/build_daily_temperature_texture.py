from __future__ import annotations

import argparse
import hashlib
import json
from collections import deque
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
MASTER_DIR = ROOT / "temperature_template" / "assets" / "vector_master"
CANVAS_SIZE = (1920, 1080)


@dataclass(frozen=True)
class Component:
    area: int
    bbox: tuple[int, int, int, int]
    centroid: tuple[float, float]
    seed: tuple[int, int]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Registra las temperaturas AEMET sobre el maestro cartografico limpio."
    )
    parser.add_argument("--date", required=True, help="Fecha ISO, por ejemplo 2026-10-06")
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Directorio de salida; por defecto assets/daily/FECHA",
    )
    parser.add_argument(
        "--report-components",
        action="store_true",
        help="Muestra los componentes geograficos detectados antes de generar.",
    )
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def atomic_save(image: Image.Image, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.stem + ".writing.png")
    image.save(temporary, format="PNG", optimize=True)
    temporary.replace(destination)


def count_nonzero(image: Image.Image) -> int:
    channel = image if image.mode == "L" else image.getchannel("A")
    return sum(1 for value in channel.get_flattened_data() if value)


def components(mask: Image.Image, minimum_area: int = 8) -> list[Component]:
    binary = mask.convert("L").point(lambda value: 1 if value >= 128 else 0)
    width, height = binary.size
    remaining = bytearray(binary.tobytes())
    found: list[Component] = []
    for start in range(width * height):
        if not remaining[start]:
            continue
        remaining[start] = 0
        queue: deque[int] = deque([start])
        area = 0
        min_x = width
        min_y = height
        max_x = 0
        max_y = 0
        sum_x = 0
        sum_y = 0
        while queue:
            index = queue.popleft()
            y, x = divmod(index, width)
            area += 1
            sum_x += x
            sum_y += y
            min_x = min(min_x, x)
            min_y = min(min_y, y)
            max_x = max(max_x, x)
            max_y = max(max_y, y)
            if x and remaining[index - 1]:
                remaining[index - 1] = 0
                queue.append(index - 1)
            if x + 1 < width and remaining[index + 1]:
                remaining[index + 1] = 0
                queue.append(index + 1)
            if y and remaining[index - width]:
                remaining[index - width] = 0
                queue.append(index - width)
            if y + 1 < height and remaining[index + width]:
                remaining[index + width] = 0
                queue.append(index + width)
        if area >= minimum_area:
            found.append(
                Component(
                    area=area,
                    bbox=(min_x, min_y, max_x + 1, max_y + 1),
                    centroid=(sum_x / area, sum_y / area),
                    seed=(start % width, start // width),
                )
            )
    return sorted(found, key=lambda item: item.area, reverse=True)


def palette_from_legend(image: Image.Image, x: int, y0: int, y1: int) -> list[tuple[int, int, int]]:
    rgb = image.convert("RGB")
    counts: dict[tuple[int, int, int], int] = {}
    for y in range(y0, y1):
        colour = rgb.getpixel((x, y))
        counts[colour] = counts.get(colour, 0) + 1
    ignored = {(255, 255, 255), (0, 0, 0), (232, 232, 232)}
    palette = [
        colour
        for colour, count in sorted(counts.items(), key=lambda item: item[1], reverse=True)
        if colour not in ignored and count >= 6
    ]
    # Las dos columnas alternas de la leyenda contienen 32 bandas exactas.
    if len(palette) < 28:
        raise ValueError(f"No se pudo leer la paleta AEMET: solo {len(palette)} colores")
    return palette[:32]


def colour_distance_sq(a: tuple[int, int, int], b: tuple[int, int, int]) -> int:
    return sum((left - right) ** 2 for left, right in zip(a, b))


def palette_mask(image: Image.Image, palette: list[tuple[int, int, int]], threshold: int = 18) -> Image.Image:
    rgb = image.convert("RGB")
    maximum_distance = threshold * threshold
    colours = set(rgb.get_flattened_data())
    lookup = {
        colour: (
            255
            if min(colour_distance_sq(colour, entry) for entry in palette)
            <= maximum_distance
            else 0
        )
        for colour in colours
    }
    output = Image.new("L", rgb.size, 0)
    output.putdata([lookup[colour] for colour in rgb.get_flattened_data()])
    return output


def nearest_palette_image(
    image: Image.Image, palette: list[tuple[int, int, int]], valid_mask: Image.Image
) -> Image.Image:
    rgb = image.convert("RGB")
    colours = set(rgb.get_flattened_data())
    lookup = {
        colour: min(palette, key=lambda entry: colour_distance_sq(colour, entry))
        for colour in colours
    }
    output = Image.new("RGB", rgb.size)
    output.putdata([lookup[colour] for colour in rgb.get_flattened_data()])
    output.putalpha(valid_mask)
    return output


def fit_crop_to_bbox(
    source: Image.Image,
    source_box: tuple[int, int, int, int],
    destination_box: tuple[int, int, int, int],
) -> Image.Image:
    width = destination_box[2] - destination_box[0]
    height = destination_box[3] - destination_box[1]
    crop = source.crop(source_box)
    crop = nearest_fill_rgba(crop, Image.new("L", crop.size, 255))
    return crop.resize((width, height), Image.Resampling.NEAREST)


def mask_for_box(mask: Image.Image, box: tuple[int, int, int, int]) -> Image.Image:
    selection = Image.new("L", mask.size, 0)
    selection.paste(mask.crop(box), box[:2])
    return selection


def composite_region(
    canvas: Image.Image,
    source: Image.Image,
    source_box: tuple[int, int, int, int],
    destination_box: tuple[int, int, int, int],
    destination_mask: Image.Image,
) -> None:
    warped = fit_crop_to_bbox(source, source_box, destination_box)
    warped_alpha = warped.getchannel("A")
    mask_crop = destination_mask.crop(destination_box)
    combined_alpha = ImageChops.multiply(warped_alpha, mask_crop)
    warped.putalpha(combined_alpha)
    canvas.alpha_composite(warped, destination_box[:2])


def warp_affine_component(
    source: Image.Image,
    destination_mask: Image.Image,
    forward: tuple[float, float, float, float, float, float],
    search_radius: int = 2,
) -> Image.Image:
    """Registra un campo completo mediante una afinidad y conserva su paleta."""
    source_rgba = source.convert("RGBA")
    source_pixels = source_rgba.load()
    source_width, source_height = source_rgba.size
    mask_pixels = destination_mask.load()
    destination = Image.new("RGBA", destination_mask.size, (0, 0, 0, 0))
    destination_pixels = destination.load()
    ax, bx, cx, ay, by, cy = forward
    determinant = ax * by - bx * ay
    if abs(determinant) < 1e-9:
        raise ValueError("La transformacion continental no es invertible")

    offsets = [(0, 0)]
    for radius in range(1, search_radius + 1):
        ring = []
        for delta in range(-radius, radius + 1):
            ring.extend(
                [(-radius, delta), (radius, delta), (delta, -radius), (delta, radius)]
            )
        offsets.extend(dict.fromkeys(ring))

    bbox = destination_mask.getbbox()
    if bbox is None:
        return destination
    for target_y in range(bbox[1], bbox[3]):
        for target_x in range(bbox[0], bbox[2]):
            if not mask_pixels[target_x, target_y]:
                continue
            shifted_x = target_x - cx
            shifted_y = target_y - cy
            source_x = (by * shifted_x - bx * shifted_y) / determinant
            source_y = (-ay * shifted_x + ax * shifted_y) / determinant
            nearest_x = round(source_x)
            nearest_y = round(source_y)
            for offset_x, offset_y in offsets:
                sample_x = nearest_x + offset_x
                sample_y = nearest_y + offset_y
                if not (0 <= sample_x < source_width and 0 <= sample_y < source_height):
                    continue
                colour = source_pixels[sample_x, sample_y]
                if colour[3]:
                    destination_pixels[target_x, target_y] = colour
                    break
    return destination


def invert_affine_point(
    target_x: float,
    target_y: float,
    forward: tuple[float, float, float, float, float, float],
) -> tuple[float, float]:
    ax, bx, cx, ay, by, cy = forward
    determinant = ax * by - bx * ay
    shifted_x = target_x - cx
    shifted_y = target_y - cy
    return (
        (by * shifted_x - bx * shifted_y) / determinant,
        (-ay * shifted_x + ax * shifted_y) / determinant,
    )


def warp_controlled_component(
    source: Image.Image,
    destination_mask: Image.Image,
    forward: tuple[float, float, float, float, float, float],
    anchors: list[tuple[str, tuple[float, float], tuple[float, float]]],
    search_radius: int = 2,
    control_grid_step: int = 8,
) -> Image.Image:
    """Deforma suavemente una afinidad mediante anclajes geograficos comunes."""
    source_rgba = source.convert("RGBA")
    source_pixels = source_rgba.load()
    source_width, source_height = source_rgba.size
    mask_pixels = destination_mask.load()
    destination = Image.new("RGBA", destination_mask.size, (0, 0, 0, 0))
    destination_pixels = destination.load()

    controls = []
    for _name, source_point, target_point in anchors:
        base_source = invert_affine_point(target_point[0], target_point[1], forward)
        controls.append(
            (
                target_point[0],
                target_point[1],
                source_point[0] - base_source[0],
                source_point[1] - base_source[1],
            )
        )

    offsets = [(0, 0)]
    for radius in range(1, search_radius + 1):
        ring = []
        for delta in range(-radius, radius + 1):
            ring.extend(
                [(-radius, delta), (radius, delta), (delta, -radius), (delta, radius)]
            )
        offsets.extend(dict.fromkeys(ring))

    def correction_at(target_x: float, target_y: float) -> tuple[float, float]:
        correction_x = 0.0
        correction_y = 0.0
        total_weight = 0.0
        for control_x, control_y, delta_x, delta_y in controls:
            distance_sq = (target_x - control_x) ** 2 + (target_y - control_y) ** 2
            if distance_sq < 1.0:
                return delta_x, delta_y
            weight = 1.0 / ((distance_sq + 225.0) ** 1.5)
            correction_x += delta_x * weight
            correction_y += delta_y * weight
            total_weight += weight
        return correction_x / total_weight, correction_y / total_weight

    bbox = destination_mask.getbbox()
    if bbox is None:
        return destination
    grid_x = list(range(bbox[0], bbox[2], control_grid_step))
    grid_y = list(range(bbox[1], bbox[3], control_grid_step))
    if grid_x[-1] != bbox[2] - 1:
        grid_x.append(bbox[2] - 1)
    if grid_y[-1] != bbox[3] - 1:
        grid_y.append(bbox[3] - 1)
    correction_grid = [
        [correction_at(grid_point_x, grid_point_y) for grid_point_x in grid_x]
        for grid_point_y in grid_y
    ]

    for target_y in range(bbox[1], bbox[3]):
        grid_row = min((target_y - bbox[1]) // control_grid_step, len(grid_y) - 2)
        y0 = grid_y[grid_row]
        y1 = grid_y[grid_row + 1]
        fraction_y = (target_y - y0) / max(1, y1 - y0)
        for target_x in range(bbox[0], bbox[2]):
            if not mask_pixels[target_x, target_y]:
                continue
            base_x, base_y = invert_affine_point(target_x, target_y, forward)
            grid_column = min((target_x - bbox[0]) // control_grid_step, len(grid_x) - 2)
            x0 = grid_x[grid_column]
            x1 = grid_x[grid_column + 1]
            fraction_x = (target_x - x0) / max(1, x1 - x0)
            top_left = correction_grid[grid_row][grid_column]
            top_right = correction_grid[grid_row][grid_column + 1]
            bottom_left = correction_grid[grid_row + 1][grid_column]
            bottom_right = correction_grid[grid_row + 1][grid_column + 1]
            top_x = top_left[0] + (top_right[0] - top_left[0]) * fraction_x
            top_y = top_left[1] + (top_right[1] - top_left[1]) * fraction_x
            bottom_x = bottom_left[0] + (bottom_right[0] - bottom_left[0]) * fraction_x
            bottom_y = bottom_left[1] + (bottom_right[1] - bottom_left[1]) * fraction_x
            correction_x = top_x + (bottom_x - top_x) * fraction_y
            correction_y = top_y + (bottom_y - top_y) * fraction_y
            nearest_x = round(base_x + correction_x)
            nearest_y = round(base_y + correction_y)
            for offset_x, offset_y in offsets:
                sample_x = nearest_x + offset_x
                sample_y = nearest_y + offset_y
                if not (0 <= sample_x < source_width and 0 <= sample_y < source_height):
                    continue
                colour = source_pixels[sample_x, sample_y]
                if colour[3]:
                    destination_pixels[target_x, target_y] = colour
                    break
    return destination


def nearest_fill_rgba(image: Image.Image, allowed_mask: Image.Image) -> Image.Image:
    """Rellena huecos propagando pixeles existentes, sin interpolar colores."""
    rgba = image.convert("RGBA")
    width, height = rgba.size
    pixels = list(rgba.get_flattened_data())
    allowed = allowed_mask.convert("L").tobytes()
    queue: deque[int] = deque()
    visited = bytearray(width * height)
    for index, colour in enumerate(pixels):
        if allowed[index] and colour[3]:
            visited[index] = 1
            queue.append(index)
    while queue:
        index = queue.popleft()
        y, x = divmod(index, width)
        neighbours = []
        if x:
            neighbours.append(index - 1)
        if x + 1 < width:
            neighbours.append(index + 1)
        if y:
            neighbours.append(index - width)
        if y + 1 < height:
            neighbours.append(index + width)
        for neighbour in neighbours:
            if allowed[neighbour] and not visited[neighbour]:
                visited[neighbour] = 1
                pixels[neighbour] = pixels[index]
                queue.append(neighbour)
    result = Image.new("RGBA", rgba.size)
    result.putdata(pixels)
    result.putalpha(allowed_mask)
    return result


def exact_component_mask(mask: Image.Image, item: Component) -> Image.Image:
    width, height = mask.size
    binary = mask.convert("L").point(lambda value: 1 if value >= 128 else 0)
    source = binary.tobytes()
    output = bytearray(width * height)
    start = item.seed[1] * width + item.seed[0]
    queue: deque[int] = deque([start])
    output[start] = 255
    while queue:
        index = queue.popleft()
        y, x = divmod(index, width)
        neighbours = []
        if x:
            neighbours.append(index - 1)
        if x + 1 < width:
            neighbours.append(index + 1)
        if y:
            neighbours.append(index - width)
        if y + 1 < height:
            neighbours.append(index + width)
        for neighbour in neighbours:
            if source[neighbour] and not output[neighbour]:
                output[neighbour] = 255
                queue.append(neighbour)
    return Image.frombytes("L", mask.size, bytes(output))


def hungarian_assignment(costs: list[list[float]]) -> list[int]:
    """Asignacion minima cuadrada; devuelve la columna elegida por cada fila."""
    size = len(costs)
    if not size or any(len(row) != size for row in costs):
        raise ValueError("La matriz de asignacion debe ser cuadrada y no vacia")
    u = [0.0] * (size + 1)
    v = [0.0] * (size + 1)
    matched_row = [0] * (size + 1)
    way = [0] * (size + 1)
    for row in range(1, size + 1):
        matched_row[0] = row
        column0 = 0
        minimum = [float("inf")] * (size + 1)
        used = [False] * (size + 1)
        while True:
            used[column0] = True
            row0 = matched_row[column0]
            delta = float("inf")
            column1 = 0
            for column in range(1, size + 1):
                if used[column]:
                    continue
                current = costs[row0 - 1][column - 1] - u[row0] - v[column]
                if current < minimum[column]:
                    minimum[column] = current
                    way[column] = column0
                if minimum[column] < delta:
                    delta = minimum[column]
                    column1 = column
            for column in range(size + 1):
                if used[column]:
                    u[matched_row[column]] += delta
                    v[column] -= delta
                else:
                    minimum[column] -= delta
            column0 = column1
            if matched_row[column0] == 0:
                break
        while True:
            column1 = way[column0]
            matched_row[column0] = matched_row[column1]
            column0 = column1
            if column0 == 0:
                break
    assignment = [-1] * size
    for column in range(1, size + 1):
        assignment[matched_row[column] - 1] = column - 1
    return assignment


def forward_affine_point(
    source_x: float,
    source_y: float,
    forward: tuple[float, float, float, float, float, float],
) -> tuple[float, float]:
    ax, bx, cx, ay, by, cy = forward
    return (
        ax * source_x + bx * source_y + cx,
        ay * source_x + by * source_y + cy,
    )


def province_centroid_anchors(
    source_valid: Image.Image,
    land_mask: Image.Image,
    mainland_mask: Image.Image,
    provinces: Image.Image,
    communities: Image.Image,
    forward: tuple[float, float, float, float, float, float],
) -> tuple[list[tuple[str, tuple[float, float], tuple[float, float]]], dict[str, float]]:
    source_regions = []
    for item in components(source_valid, 100):
        x, y = item.centroid
        if x >= 580:
            continue
        if y >= 430:
            continue
        if item.area > 10000 and (x < 180 or y < 80):
            continue
        if x > 470 and y > 200:
            continue
        source_regions.append(item)

    boundary = ImageChops.lighter(
        provinces.getchannel("A"), communities.getchannel("A")
    ).point(lambda value: 255 if value > 20 else 0)
    boundary = boundary.filter(ImageFilter.MaxFilter(3))
    target_interior = ImageChops.multiply(
        ImageChops.subtract(land_mask, boundary), mainland_mask
    )
    target_regions = [item for item in components(target_interior, 1000)]
    if len(source_regions) != 47 or len(target_regions) != 47:
        raise ValueError(
            "No se detectaron las 47 provincias peninsulares esperadas: "
            f"origen={len(source_regions)}, destino={len(target_regions)}"
        )

    costs = []
    for source_region in source_regions:
        projected = forward_affine_point(*source_region.centroid, forward)
        row = []
        for target_region in target_regions:
            distance_sq = (
                (projected[0] - target_region.centroid[0]) ** 2
                + (projected[1] - target_region.centroid[1]) ** 2
            )
            row.append(distance_sq)
        costs.append(row)
    assignment = hungarian_assignment(costs)
    anchors = []
    distances = []
    for index, target_index in enumerate(assignment):
        source_region = source_regions[index]
        target_region = target_regions[target_index]
        anchors.append(
            (
                f"provincia_{index + 1:02d}",
                source_region.centroid,
                target_region.centroid,
            )
        )
        distances.append(costs[index][target_index] ** 0.5)
    metrics = {
        "count": float(len(anchors)),
        "mean_initial_distance": sum(distances) / len(distances),
        "maximum_initial_distance": max(distances),
    }
    return anchors, metrics


def main() -> int:
    args = parse_args()
    raw_dir = ROOT / "data" / "raw" / args.date
    peninsula_path = raw_dir / "temperaturas_maximas.png"
    canaries_path = raw_dir / "temperaturas_maximas_canarias.png"
    master_mask_path = MASTER_DIR / "mascara_temperatura.png"
    provinces_path = MASTER_DIR / "provincias.png"
    communities_path = MASTER_DIR / "comunidades.png"
    required = [peninsula_path, canaries_path, master_mask_path, provinces_path, communities_path]
    for path in required:
        if not path.exists() or path.stat().st_size == 0:
            raise FileNotFoundError(path)

    peninsula = Image.open(peninsula_path).convert("RGB")
    canaries = Image.open(canaries_path).convert("RGB")
    if peninsula.size != (630, 500) or canaries.size != (730, 370):
        raise ValueError(
            f"Dimensiones AEMET inesperadas: peninsula={peninsula.size}, canarias={canaries.size}"
        )
    land_mask = Image.open(master_mask_path).convert("L")
    if land_mask.size != CANVAS_SIZE:
        raise ValueError(f"La mascara maestra mide {land_mask.size}, no {CANVAS_SIZE}")

    target_components = components(land_mask)
    pen_palette = palette_from_legend(peninsula, 590, 8, 476)
    can_palette = palette_from_legend(canaries, 694, 8, 348)
    pen_valid = palette_mask(peninsula, pen_palette)
    can_valid = palette_mask(canaries, can_palette)

    if args.report_components:
        print("TARGET")
        for index, item in enumerate(target_components[:30]):
            print(index, item)
        print("PENINSULA VALID")
        for index, item in enumerate(components(pen_valid, 15)[:30]):
            print(index, item)
        print("CANARIAS VALID")
        for index, item in enumerate(components(can_valid, 15)[:30]):
            print(index, item)

    pen_clean = nearest_palette_image(peninsula, pen_palette, pen_valid)
    can_clean = nearest_palette_image(canaries, can_palette, can_valid)
    provinces = Image.open(provinces_path).convert("RGBA")
    # La capa de comunidades se conserva solo como guia geometrica interna para
    # detectar las 47 provincias durante el registro. No debe renderizarse en
    # temperatura_con_limites.png: la textura termica ya separa las comunidades
    # y superponerla produciria contornos dobles.
    communities = Image.open(communities_path).convert("RGBA")

    # Registro inicial. Los archipielagos se tratan de forma independiente porque
    # su colocacion en el maestro es editorial, no una proyeccion geografica unica.
    temperature = Image.new("RGBA", CANVAS_SIZE, (0, 0, 0, 0))
    mainland = target_components[0]
    mainland_box = mainland.bbox
    mainland_mask = exact_component_mask(land_mask, mainland)
    # Afinidad calculada con tres puntos homologos del contorno: cabo Fisterra,
    # cabo de Creus y punta de Tarifa. Incluye el giro/cizalla que el ajuste por
    # rectangulo no podia representar.
    mainland_forward = (
        2.55671593,
        -0.33588518,
        315.63533646,
        0.14800720,
        2.44004632,
        -81.32952769,
    )
    mainland_anchors, province_anchor_metrics = province_centroid_anchors(
        pen_valid,
        land_mask,
        mainland_mask,
        provinces,
        communities,
        mainland_forward,
    )
    mainland_anchors.extend(
        [
            ("cabo_fisterra", (73, 108), (466, 193)),
            ("cabo_de_creus", (500, 128), (1551, 305)),
            # La punta termica real de Tarifa esta en x=188. El punto x=211 que
            # se uso inicialmente ya pertenece al mar gris del PNG de AEMET.
            ("punta_de_tarifa", (188, 431), (710, 1004)),
        ]
    )
    mainland_registered = warp_controlled_component(
        pen_clean,
        mainland_mask,
        mainland_forward,
        mainland_anchors,
        search_radius=3,
        control_grid_step=8,
    )
    temperature = Image.alpha_composite(temperature, mainland_registered)

    balearic_components = [
        item
        for item in target_components[1:]
        if item.centroid[0] > 1300 and 500 < item.centroid[1] < 800
    ]
    if len(balearic_components) != 4:
        raise ValueError(f"Se esperaban 4 componentes baleares y hay {len(balearic_components)}")
    mallorca = max(balearic_components, key=lambda item: item.area)
    menorca = max(balearic_components, key=lambda item: item.centroid[0])
    formentera = max(balearic_components, key=lambda item: item.centroid[1])
    ibiza = next(
        item
        for item in balearic_components
        if item not in {mallorca, menorca, formentera}
    )
    balearic_mappings = [
        (mallorca, (480, 212, 534, 275)),
        (menorca, (533, 211, 565, 243)),
        (ibiza, (440, 272, 469, 301)),
        (formentera, (447, 296, 463, 312)),
    ]
    for item, source_box in balearic_mappings:
        composite_region(
            temperature,
            pen_clean,
            source_box,
            item.bbox,
            exact_component_mask(land_mask, item),
        )

    canary_components = sorted(
        (
            item
            for item in target_components[1:]
            if item.centroid[0] < 700 and item.centroid[1] > 850
        ),
        key=lambda item: item.centroid[0],
    )
    if len(canary_components) != 7:
        raise ValueError(f"Se esperaban 7 componentes canarios y hay {len(canary_components)}")
    canary_source_boxes = [
        (26, 272, 66, 306),    # El Hierro
        (52, 118, 92, 184),    # La Palma
        (136, 218, 173, 252),  # La Gomera
        (193, 163, 305, 256),  # Tenerife
        (338, 226, 406, 297),  # Gran Canaria
        (517, 132, 610, 247),  # Fuerteventura
        (596, 57, 661, 125),   # Lanzarote
    ]
    for item, source_box in zip(canary_components, canary_source_boxes):
        composite_region(
            temperature,
            can_clean,
            source_box,
            item.bbox,
            exact_component_mask(land_mask, item),
        )

    temperature.putalpha(ImageChops.multiply(temperature.getchannel("A"), land_mask))
    output_colours = {
        colour[:3]
        for colour in temperature.get_flattened_data()
        if colour[3]
    }
    authorised_colours = set(pen_palette) | set(can_palette)
    invented_colours = output_colours - authorised_colours
    if invented_colours:
        raise ValueError(f"La textura contiene {len(invented_colours)} colores no autorizados")
    alpha = temperature.getchannel("A")
    missing_mask = ImageChops.subtract(land_mask, alpha)
    land_pixels = count_nonzero(land_mask)
    covered_pixels = count_nonzero(alpha)
    missing_pixels = count_nonzero(missing_mask)
    coverage_percent = covered_pixels * 100.0 / land_pixels
    if coverage_percent < 99.0:
        raise ValueError(
            f"La cobertura termica es insuficiente: {coverage_percent:.3f}%"
        )
    with_boundaries = Image.alpha_composite(temperature, provinces)
    preview = Image.alpha_composite(
        Image.new("RGBA", CANVAS_SIZE, (226, 239, 248, 255)), with_boundaries
    ).convert("RGB")

    output_dir = (
        args.output_dir.resolve()
        if args.output_dir
        else ROOT / "temperature_template" / "assets" / "daily" / args.date
    )
    outputs = {
        "temperatura_rellenada.png": temperature,
        "temperatura_con_limites.png": with_boundaries,
        "preview_registro.png": preview,
    }
    for name, image in outputs.items():
        atomic_save(image, output_dir / name)

    manifest = {
        "phase": "daily_temperature_registration",
        "status": "prototype_pending_visual_review",
        "date": args.date,
        "canvas_size": list(CANVAS_SIZE),
        "inputs": {
            str(path.relative_to(ROOT)).replace("\\", "/"): sha256(path)
            for path in required
        },
        "palette": {
            "peninsula_colours": len(pen_palette),
            "canary_colours": len(can_palette),
            "resampling": "nearest",
            "colour_grading": False,
            "output_unique_colours": len(output_colours),
            "invented_colours": 0,
        },
        "boundaries": {
            "rendered_layers": ["provincias.png"],
            "registration_only_layers": ["comunidades.png"],
        },
        "coverage": {
            "land_pixels": land_pixels,
            "covered_pixels": covered_pixels,
            "missing_pixels": missing_pixels,
            "coverage_percent": coverage_percent,
            "missing_bbox": list(missing_mask.getbbox()) if missing_mask.getbbox() else None,
        },
        "registration": {
            "mainland": {
                "method": "province_centroid_controlled_continuous_warp",
                "source_anchors": {
                    "cabo_fisterra": [73, 108],
                    "cabo_de_creus": [500, 128],
                    "punta_de_tarifa": [188, 431]
                },
                "destination_anchors": {
                    "cabo_fisterra": [466, 193],
                    "cabo_de_creus": [1551, 305],
                    "punta_de_tarifa": [710, 1004]
                },
                "forward_affine": list(mainland_forward),
                "elastic_control_points": len(mainland_anchors),
                "province_anchor_metrics": province_anchor_metrics,
                "elastic_method": "inverse_distance_weighted_continuous_warp",
                "control_grid_step_pixels": 8,
                "boundary_gap_search_radius_source_pixels": 3,
                "destination_box": list(mainland_box),
            },
            "balearic_islands": 4,
            "canary_islands": 7,
            "island_strategy": "independent_nearest_neighbour",
        },
        "outputs": {
            name: {
                "path": str((output_dir / name).relative_to(ROOT)).replace("\\", "/"),
                "sha256": sha256(output_dir / name),
                "mode": image.mode,
            }
            for name, image in outputs.items()
        },
    }
    manifest_path = ROOT / "temperature_template" / "validation" / f"registration_{args.date}.json"
    temporary = manifest_path.with_suffix(".writing.json")
    temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(manifest_path)
    print(output_dir)
    print(manifest_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
