"""Read the editable zone artwork in the PDF-compatible Illustrator file.

The PDF form identifiers are stable only for an unchanged source file.  They
are deliberately *not* interpreted as AEMET zone codes here.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader
from pypdf.generic import ContentStream


@dataclass(frozen=True)
class IllustratorShape:
    form_id: str
    layer: str
    polygons: tuple[tuple[tuple[float, float], ...], ...]
    bounds: tuple[float, float, float, float]
    area: float


def illustrator_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_illustrator_shapes(path: Path) -> list[IllustratorShape]:
    reader = PdfReader(path)
    if len(reader.pages) != 1:
        raise ValueError("El mapa de Illustrator debe tener una sola página")
    page = reader.pages[0]
    if [float(value) for value in page.mediabox] != [0, 0, 1920, 1080]:
        raise ValueError("La mesa de trabajo de Illustrator debe medir 1920×1080")
    resources = page["/Resources"]
    layer_names = {
        key: str(value.get_object()["/Name"])
        for key, value in resources["/Properties"].items()
    }
    forms = resources["/XObject"]
    current_layer: str | None = None
    result: list[IllustratorShape] = []
    seen: set[str] = set()
    for operands, operator in ContentStream(page["/Contents"], reader).operations:
        if operator == b"BDC" and len(operands) == 2 and operands[0] == "/OC":
            current_layer = layer_names.get(operands[1])
        elif operator == b"EMC":
            current_layer = None
        elif operator == b"Do" and current_layer is not None:
            form_id = str(operands[0]).removeprefix("/")
            if form_id in seen:
                raise ValueError(f"Forma repetida en Illustrator: {form_id}")
            seen.add(form_id)
            form = forms[operands[0]].get_object()
            polygons = _shape_polygons(form, reader)
            if not polygons:
                continue
            points = [point for polygon in polygons for point in polygon]
            bounds = (
                min(point[0] for point in points),
                min(point[1] for point in points),
                max(point[0] for point in points),
                max(point[1] for point in points),
            )
            area = sum(abs(_signed_area(polygon)) for polygon in polygons)
            result.append(IllustratorShape(form_id, current_layer, polygons, bounds, area))
    return result


def _shape_polygons(form, reader: PdfReader) -> tuple[tuple[tuple[float, float], ...], ...]:
    """Flatten filled paths, or strokes for outline-only forms, to page coordinates."""
    matrix = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    stack = []
    subpaths: list[list[tuple[float, float]]] = []
    active: list[tuple[float, float]] = []
    current = (0.0, 0.0)
    result: list[tuple[tuple[float, float], ...]] = []
    strokes: list[tuple[tuple[float, float], ...]] = []

    def move(x: float, y: float) -> None:
        nonlocal active, current
        if active:
            subpaths.append(active)
        current = (x, y)
        active = [_transform(matrix, x, y)]

    def line(x: float, y: float) -> None:
        nonlocal current
        current = (x, y)
        active.append(_transform(matrix, x, y))

    for args, op in ContentStream(form, reader).operations:
        if op == b"q":
            stack.append(matrix)
        elif op == b"Q":
            matrix = stack.pop()
        elif op == b"cm":
            matrix = _multiply(matrix, tuple(float(value) for value in args))
        elif op == b"m":
            move(float(args[0]), float(args[1]))
        elif op == b"l":
            line(float(args[0]), float(args[1]))
        elif op in (b"c", b"v", b"y"):
            if op == b"c":
                c1 = (float(args[0]), float(args[1]))
                c2 = (float(args[2]), float(args[3]))
                end = (float(args[4]), float(args[5]))
            elif op == b"v":
                c1 = current
                c2 = (float(args[0]), float(args[1]))
                end = (float(args[2]), float(args[3]))
            else:
                c1 = (float(args[0]), float(args[1]))
                c2 = end = (float(args[2]), float(args[3]))
            start = current
            for step in range(1, 9):
                t = step / 8
                u = 1 - t
                x = u**3 * start[0] + 3*u*u*t*c1[0] + 3*u*t*t*c2[0] + t**3*end[0]
                y = u**3 * start[1] + 3*u*u*t*c1[1] + 3*u*t*t*c2[1] + t**3*end[1]
                active.append(_transform(matrix, x, y))
            current = end
        elif op == b"re":
            x, y, width, height = (float(value) for value in args)
            move(x, y)
            for point in ((x+width, y), (x+width, y+height), (x, y+height)):
                line(*point)
        elif op in (b"f", b"f*", b"B", b"B*", b"b", b"b*"):
            if active:
                subpaths.append(active)
            result.extend(tuple(path) for path in subpaths if len(path) >= 3)
            active, subpaths = [], []
        elif op in (b"S", b"s"):
            if active:
                subpaths.append(active)
            strokes.extend(tuple(path) for path in subpaths if len(path) >= 3)
            active, subpaths = [], []
        elif op == b"n":
            active, subpaths = [], []
    return tuple(result or strokes)


def _transform(matrix, x: float, y: float) -> tuple[float, float]:
    a, b, c, d, e, f = matrix
    return a*x+c*y+e, 1080-(b*x+d*y+f)


def _multiply(first, second):
    a, b, c, d, e, f = first
    g, h, i, j, k, l = second
    return (a*g+c*h, b*g+d*h, a*i+c*j, b*i+d*j, a*k+c*l+e, b*k+d*l+f)


def _signed_area(points) -> float:
    return sum(
        left[0]*right[1]-right[0]*left[1]
        for left, right in zip(points, points[1:]+points[:1])
    ) / 2
