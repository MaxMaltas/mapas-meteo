"""Build a checked AEMET zone reference from named Illustrator artwork.

The Illustrator PDF layer names contain only four broad groups.  Individual
object names are in its compressed, editable Illustrator payload.  This tool
reads those names and their exact paths once; the daily renderer uses the
resulting JSON and refuses an AI file whose checksum has changed.
"""

from __future__ import annotations

import argparse
import ctypes
import ctypes.util
import hashlib
import json
import re
import sys
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from meteo_pipeline.illustrator_map import read_illustrator_shapes  # noqa: E402
from tools.build_alert_zone_face_reference import _read_cap_snapshots, _minimum_cost_assignment  # noqa: E402

UID = re.compile(rb"%_/XMLUID\s*:\s*\(([^)]*)\)")
CODE = re.compile(r"^_x([0-9A-Fa-f]{2})_([0-9]{5})_(.+)$")
AS = re.compile(rb"(?m)^\d+ As\s*$")
COMMAND = re.compile(rb"(?m)^\s*([0-9eE+., -]+)\s+(m|C|L|l|c)\s*$")
OP = re.compile(rb"(?m)^\s*(b|B|U)\s*$")

# These two leaf objects were given the adjacent zone's code in Illustrator.
# Their artwork and CAP polygon centroids show an unambiguous west/east split.
SOURCE_LABEL_CORRECTIONS = {
    "_x36_11802_Guadix_y_Baza_00000082334587163038902110000011541571474244539308_": "611801",
    "_x36_81903_Alcarria_de_Guadalajara_00000029741242863680874490000016820589556947375802_": "681902",
}

# The parent Illustrator groups carry the code; their child objects do not.
GROUP_CHILD_CODES = {
    "Ibiza": "645301",
    "Formentera": "645301",
    "Lanzarote_01": "659101",
    "Lanzarote_02": "659101",
}


def _zstd_library() -> ctypes.CDLL:
    candidates = [ctypes.util.find_library("zstd")]
    runtime = Path(sys.executable).resolve().parents[1]
    candidates += list(runtime.glob("native/poppler/Library/bin/zstd.dll"))
    candidates += list(runtime.glob("**/zstd.dll"))
    for candidate in candidates:
        if candidate:
            try:
                return ctypes.CDLL(str(candidate))
            except OSError:
                pass
    raise RuntimeError("Falta libzstd: no se puede leer el archivo editable Illustrator")


def _private_artwork(ai_path: Path) -> bytes:
    page = PdfReader(ai_path).pages[0]
    private = page["/PieceInfo"]["/Illustrator"]["/Private"].get_object()
    streams = sorted(
        (int(key.removeprefix("/AIPrivateData")), value)
        for key, value in private.items()
        if key.startswith("/AIPrivateData")
    )
    data = b"".join(value.get_object().get_data() for _, value in streams)
    start = data.find(b"\x28\xb5\x2f\xfd")
    if start < 0:
        raise ValueError("No se encuentra el contenido editable Zstandard de Illustrator")
    frame = data[start:]
    try:
        import zstandard

        return zstandard.ZstdDecompressor().decompress(frame, max_output_size=50_000_000)
    except ImportError:
        pass
    lib = _zstd_library()
    lib.ZSTD_getFrameContentSize.argtypes = (ctypes.c_void_p, ctypes.c_size_t)
    lib.ZSTD_getFrameContentSize.restype = ctypes.c_ulonglong
    lib.ZSTD_findFrameCompressedSize.argtypes = (ctypes.c_void_p, ctypes.c_size_t)
    lib.ZSTD_findFrameCompressedSize.restype = ctypes.c_size_t
    lib.ZSTD_decompress.argtypes = (ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t)
    lib.ZSTD_decompress.restype = ctypes.c_size_t
    lib.ZSTD_isError.argtypes = (ctypes.c_size_t,)
    lib.ZSTD_isError.restype = ctypes.c_uint
    size = lib.ZSTD_getFrameContentSize(frame, len(frame))
    if size > 50_000_000:
        # Illustrator emits a Zstandard frame without a declared content size.
        size = 64_000_000
    output = ctypes.create_string_buffer(size)
    written = lib.ZSTD_decompress(output, size, frame, lib.ZSTD_findFrameCompressedSize(frame, len(frame)))
    if lib.ZSTD_isError(written):
        raise ValueError("No se pudo descomprimir el contenido de Illustrator")
    return output.raw[:written]


def _decode_uid(raw: bytes) -> str:
    value = raw.decode("latin-1")
    value = re.sub(r"_x([0-9A-Fa-f]{2,4})_", lambda m: chr(int(m.group(1), 16)), value)
    return value


def _flatten_path(segment: bytes) -> list[list[list[float]]]:
    polygons: list[list[list[float]]] = []
    active: list[list[float]] = []
    current: tuple[float, float] | None = None

    def point(x: float, y: float) -> list[float]:
        return [round(x + 360, 3), round(990 - y, 3)]

    for match in COMMAND.finditer(segment):
        values = [float(v) for v in match.group(1).split()]
        op = match.group(2)
        if op == b"m":
            if len(active) >= 3:
                polygons.append(active)
            active = [point(values[0], values[1])]
            current = (values[0], values[1])
        elif op in (b"L", b"l") and current is not None:
            current = (values[-2], values[-1])
            active.append(point(*current))
        elif op in (b"C", b"c") and current is not None:
            x0, y0 = current
            x1, y1, x2, y2, x3, y3 = values
            for step in range(1, 9):
                t = step / 8
                u = 1 - t
                x = u**3*x0 + 3*u*u*t*x1 + 3*u*t*t*x2 + t**3*x3
                y = u**3*y0 + 3*u*u*t*y1 + 3*u*t*t*y2 + t**3*y3
                active.append(point(x, y))
            current = (x3, y3)
    if len(active) >= 3:
        polygons.append(active)
    return polygons


def _art_objects(ai_path: Path) -> list[dict]:
    raw = _private_artwork(ai_path).replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    as_starts = [m.end() for m in AS.finditer(raw)]
    import bisect

    objects: list[dict] = []
    for match in UID.finditer(raw):
        name = match.group(1).decode("latin-1")
        before = raw[max(0, match.start()-300):match.start()]
        ops = list(OP.finditer(before))
        if not ops:
            continue
        kind = ops[-1].group(1).decode("ascii")
        code_match = CODE.match(name)
        code = chr(int(code_match.group(1), 16)) + code_match.group(2) if code_match else GROUP_CHILD_CODES.get(name)
        polygons: list[list[list[float]]] = []
        if kind in ("b", "B"):
            index = bisect.bisect_right(as_starts, match.start()) - 1
            if index >= 0:
                polygons = _flatten_path(raw[as_starts[index]:match.start()])
        objects.append({"uid": name, "code": code, "kind": kind, "polygons": polygons})
    return objects


def _cap_zones(cap_path: Path) -> tuple[str, dict]:
    snapshots = _read_cap_snapshots(cap_path)
    complete = [(sent, zones) for sent, zones in snapshots.items() if len(zones) == 233]
    if not complete:
        raise ValueError("El CAP no contiene una instantánea completa de 182+51 zonas")
    return max(complete, key=lambda item: item[0])


def _centroid(polygons: list) -> tuple[float, float]:
    points = [point for polygon in polygons for point in polygon]
    return (sum(p[0] for p in points)/len(points), sum(p[1] for p in points)/len(points))


def build_reference(ai_path: Path, cap_path: Path) -> dict:
    import numpy as np

    source_objects = _art_objects(ai_path)
    sent, cap = _cap_zones(cap_path)
    land: dict[str, dict] = {}
    pending: list[dict] = []
    province_by_code: dict[str, str] = {}
    for item in source_objects:
        code = SOURCE_LABEL_CORRECTIONS.get(item["uid"], item["code"])
        if code and item["polygons"]:
            if code not in cap:
                raise ValueError(f"Código en Illustrator ausente en AEMET: {code}")
            pending.append({**item, "code": code})
            zone = land.setdefault(code, {"code": code, "name": cap[code]["name"], "province": "", "parts": []})
            zone["parts"].append({"uid": item["uid"], "polygons": item["polygons"]})
        elif item["kind"] == "U" and not code and pending and item["uid"] not in ("Peninsula", "ZONAS_AEMET", "MAR", "PROVINCIAS", "CCAA"):
            province = _decode_uid(item["uid"].encode("latin-1")).replace("_", " ")
            for child in pending:
                province_by_code[child["code"]] = province
            pending.clear()
    for code, province in province_by_code.items():
        land[code]["province"] = province

    expected_land = {code for code in cap if not code.endswith("C")}
    if set(land) != expected_land:
        raise ValueError(f"Zonas terrestres sin dibujo: {sorted(expected_land-set(land))}; códigos inesperados: {sorted(set(land)-expected_land)}")

    # Assign the 51 sea forms by geographic-to-artwork affine registration.
    # The terrestrial named objects are control points; mainland and island
    # insets are separate coordinate systems.
    all_shapes = read_illustrator_shapes(ai_path)
    shapes = [s for s in all_shapes if s.layer == "MAR"]
    province_shapes = [s for s in all_shapes if s.layer == "PROVINCIAS"]
    community_shapes = [s for s in all_shapes if s.layer == "CCAA"]
    if len(shapes) != 51:
        raise ValueError(f"Se esperaban 51 formas marítimas; hay {len(shapes)}")
    # Illustrator puede consolidar piezas insulares o enclaves en un mismo objeto
    # al guardar el documento. La geometria sigue siendo valida aunque cambie el
    # numero de objetos PDF; exigimos al menos las 50 provincias y las 17 CCAA.
    if len(province_shapes) < 50 or len(community_shapes) < 17:
        raise ValueError(
            "Faltan contornos de provincias o comunidades en Illustrator: "
            f"provincias={len(province_shapes)}, comunidades={len(community_shapes)}"
        )
    fits = {}
    for region in ("mainland", "canarias"):
        geo = []
        art = []
        for code, zone in land.items():
            if code.startswith("65") != (region == "canarias"):
                continue
            cap_points = [p for poly in cap[code]["polygons"] for p in poly]
            if not cap_points:
                continue
            geo.append([sum(p[1] for p in cap_points)/len(cap_points), sum(p[0] for p in cap_points)/len(cap_points), 1])
            art.append(_centroid([poly for part in zone["parts"] for poly in part["polygons"]]))
        fits[region], *_ = np.linalg.lstsq(np.array(geo), np.array(art), rcond=None)
        residuals = np.linalg.norm(np.array(geo) @ fits[region] - np.array(art), axis=1)
        if max(residuals) > 45:
            raise ValueError(
                f"Código terrestre posiblemente asignado a la zona equivocada en {region}: "
                f"residuo máximo {max(residuals):.1f} px"
            )
    marine_codes = sorted(code for code in cap if code.endswith("C"))
    costs = []
    for code in marine_codes:
        points = [p for poly in cap[code]["polygons"] for p in poly]
        lat = sum(p[0] for p in points)/len(points)
        lon = sum(p[1] for p in points)/len(points)
        fit = fits["canarias" if code.startswith("65") else "mainland"]
        target = np.array([lon, lat, 1]) @ fit
        costs.append([float((target[0]-(s.bounds[0]+s.bounds[2])/2)**2 + (target[1]-(s.bounds[1]+s.bounds[3])/2)**2) for s in shapes])
    assignment = _minimum_cost_assignment(costs)
    marine = []
    for row, col in enumerate(assignment):
        code = marine_codes[row]
        shape = shapes[col]
        if costs[row][col]**0.5 > 45:
            raise ValueError(f"Zona marítima {code} sin contorno fiable ({costs[row][col]**0.5:.1f} px)")
        marine.append({"code": code, "name": cap[code]["name"], "form_id": shape.form_id, "polygons": [[[round(x, 3), round(y, 3)] for x, y in poly] for poly in shape.polygons], "centroid_distance_px": round(costs[row][col]**0.5, 2)})

    return {
        "schema_version": 4,
        "source": ai_path.name,
        "source_sha256": hashlib.sha256(ai_path.read_bytes()).hexdigest(),
        "source_cap": str(cap_path.resolve().relative_to(ROOT.resolve())).replace("\\", "/"),
        "source_cap_snapshot": sent,
        "assignment_method": "Illustrator object UID; two documented adjacent-code corrections; marine affine matching",
        "source_label_corrections": SOURCE_LABEL_CORRECTIONS,
        "land_zone_count": len(land),
        "marine_zone_count": len(marine),
        "province_outline_count": len(province_shapes),
        "community_outline_count": len(community_shapes),
        "land_zones": [land[code] for code in sorted(land)],
        "marine_zones": marine,
        "province_outlines": [
            {"form_id": shape.form_id, "polygons": [[[round(x, 3), round(y, 3)] for x, y in polygon] for polygon in shape.polygons]}
            for shape in province_shapes
        ],
        "community_outlines": [
            {"form_id": shape.form_id, "polygons": [[[round(x, 3), round(y, 3)] for x, y in polygon] for polygon in shape.polygons]}
            for shape in community_shapes
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--illustrator", type=Path, default=ROOT / "MAPA_ALERTAS_ILUSTRATOR.ai")
    parser.add_argument("--cap", type=Path, default=ROOT / "data/raw/2026-10-01/avisos_cap.data.tar")
    parser.add_argument("--output", type=Path, default=ROOT / "config/alert_zone_faces.illustrator.reference.json")
    args = parser.parse_args()
    reference = build_reference(args.illustrator, args.cap)
    args.output.write_text(json.dumps(reference, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{args.output}: {reference['land_zone_count']} tierra; {reference['marine_zone_count']} mar")


if __name__ == "__main__":
    main()
