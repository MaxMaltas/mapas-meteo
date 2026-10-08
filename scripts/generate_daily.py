from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from meteo_pipeline.aemet import (
    AemetClient,
    AemetError,
    TEMPERATURE_MAXIMA_CANARY_PAGE_URL,
    TEMPERATURE_MAXIMA_PAGE_URL,
    decode_json_payload,
    save_download,
    save_image_download,
)
from meteo_pipeline.illustrator_alerts import render_illustrator_alert_map
from meteo_pipeline.alerts import summarise_cap_by_province, summarise_cap_by_zone
from meteo_pipeline.normalize import build_daily_document, validate_config


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        os.environ.setdefault(name.strip(), value.strip().strip('"').strip("'"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Descarga AEMET y genera el JSON diario para After Effects."
    )
    parser.add_argument("--config", type=Path, default=ROOT / "config" / "meteo.json")
    parser.add_argument("--date", type=date.fromisoformat, default=date.today())
    parser.add_argument("--validate", action="store_true", help="Solo valida la configuración")
    parser.add_argument(
        "--reuse-raw",
        action="store_true",
        help="Regenera el JSON usando las descargas ya guardadas para la fecha",
    )
    parser.add_argument(
        "--alerts-as-of",
        type=datetime.fromisoformat,
        help=(
            "Instante con zona horaria para excluir avisos ya caducados; "
            "por defecto se usa la hora actual solo al generar la fecha de hoy"
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.config.exists():
        print(
            f"No existe {args.config}. Copia config/meteo.example.json como config/meteo.json "
            "y completa los municipios de cada posición.",
            file=sys.stderr,
        )
        return 2

    config = json.loads(args.config.read_text(encoding="utf-8-sig"))
    problems = validate_config(config)
    if problems:
        print("Configuración incompleta:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 2
    if args.validate:
        print("Configuración válida")
        return 0

    raw_dir = ROOT / "data" / "raw" / args.date.isoformat()
    if args.reuse_raw:
        daily_payload, _ = read_raw_product(raw_dir, "municipios_diaria")
        hourly_payload, _ = read_raw_product(raw_dir, "municipios_horaria")
        alerts_payload, alerts_path = read_raw_product(raw_dir, "avisos_cap")
        temperature_map_paths = find_temperature_maps(raw_dir)
    else:
        load_dotenv(ROOT / ".env")
        api_key = os.environ.get("AEMET_API_KEY", "")
        api_key_file = ROOT / "api.txt"
        if not api_key and api_key_file.exists():
            api_key = api_key_file.read_text(encoding="utf-8-sig").strip()
        client = AemetClient(api_key)
        daily_download = client.download_product(
            "/api/prediccion/especifica/municipio/diaria/todos"
        )
        hourly_download = client.download_product(
            "/api/prediccion/especifica/municipio/horaria/todos"
        )
        alerts_download = client.download_product(
            "/api/avisos_cap/ultimoelaborado/area/esp"
        )
        save_download(daily_download, raw_dir, "municipios_diaria")
        save_download(hourly_download, raw_dir, "municipios_horaria")
        alerts_path = save_download(alerts_download, raw_dir, "avisos_cap")
        temperature_map_paths = download_temperature_maps(client, raw_dir)
        daily_payload = daily_download.payload
        hourly_payload = hourly_download.payload
        alerts_payload = alerts_download.payload

    local_now = datetime.now(ZoneInfo("Europe/Madrid"))
    alert_as_of = args.alerts_as_of
    if alert_as_of is None and args.date == local_now.date():
        alert_as_of = local_now
    if alert_as_of is not None and alert_as_of.utcoffset() is None:
        print("--alerts-as-of debe incluir un huso horario", file=sys.stderr)
        return 2
    alerts_summary = summarise_cap_by_province(
        alerts_payload, args.date, as_of=alert_as_of
    )
    zone_summary = summarise_cap_by_zone(
        alerts_payload, args.date, as_of=alert_as_of
    )
    alerts_summary["zone_criterion"] = zone_summary["criterion"]
    alerts_summary["zones"] = zone_summary["zones"]

    document = build_daily_document(
        decode_json_payload(daily_payload),
        decode_json_payload(hourly_payload),
        config,
        args.date,
        str(alerts_path.relative_to(ROOT)).replace("\\", "/"),
        alerts_summary,
    )

    output_dir = ROOT / "data" / "generated" / args.date.isoformat()
    output_dir.mkdir(parents=True, exist_ok=True)
    alert_map_path = output_dir / "alertas.png"
    render_illustrator_alert_map(
        ROOT / "MAPA_ALERTAS_ILUSTRATOR.ai",
        ROOT / "config" / "alert_zone_faces.illustrator.reference.json",
        zone_summary["zones"],
        alert_map_path,
        width=config.get("output", {}).get("width", 1920),
        height=config.get("output", {}).get("height", 1080),
    )
    document["alerts"]["map_status"] = "ready"
    document["alerts"]["map_file"] = str(alert_map_path.relative_to(ROOT)).replace(
        "\\", "/"
    )
    output_path = output_dir / "meteo.json"
    output_path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    output_map_paths = []
    for temperature_map_path in temperature_map_paths:
        output_map_path = output_dir / temperature_map_path.name
        shutil.copy2(temperature_map_path, output_map_path)
        output_map_paths.append(output_map_path)
    latest_dir = ROOT / "data" / "generated" / "latest"
    latest_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(output_path, latest_dir / "meteo.json")
    shutil.copy2(alert_map_path, latest_dir / alert_map_path.name)
    for temperature_map_path in temperature_map_paths:
        shutil.copy2(temperature_map_path, latest_dir / temperature_map_path.name)

    print(output_path)
    print(alert_map_path)
    for output_map_path in output_map_paths:
        print(output_map_path)
    if document["warnings"]:
        print(f"Generado con {len(document['warnings'])} avisos de validación")
    return 0


def read_raw_product(directory: Path, stem: str) -> tuple[bytes, Path]:
    matches = sorted(directory.glob(f"{stem}.data*"))
    if not matches:
        raise FileNotFoundError(
            f"No existe una descarga previa para {stem} en {directory}"
        )
    path = matches[0]
    return path.read_bytes(), path


def find_raw_file(directory: Path, stem: str) -> Path | None:
    matches = sorted(directory.glob(f"{stem}.*"))
    return matches[0] if matches else None


def find_temperature_maps(directory: Path) -> list[Path]:
    paths = []
    for stem, label in (
        ("temperaturas_maximas", "Península y Baleares"),
        ("temperaturas_maximas_canarias", "Canarias"),
    ):
        path = find_raw_file(directory, stem)
        if path is None:
            print(
                f"Aviso: la descarga reutilizada no contiene el mapa de {label}",
                file=sys.stderr,
            )
        else:
            paths.append(path)
    return paths


def download_temperature_maps(client: AemetClient, directory: Path) -> list[Path]:
    paths = []
    maps = (
        ("temperaturas_maximas", "Península y Baleares", TEMPERATURE_MAXIMA_PAGE_URL),
        (
            "temperaturas_maximas_canarias",
            "Canarias",
            TEMPERATURE_MAXIMA_CANARY_PAGE_URL,
        ),
    )
    for stem, label, page_url in maps:
        try:
            download = client.download_temperature_maxima_map(page_url)
            paths.append(save_image_download(download, directory, stem))
        except AemetError as error:
            print(
                f"Aviso: no se pudo descargar el mapa de {label}: {error}",
                file=sys.stderr,
            )
    return paths


if __name__ == "__main__":
    raise SystemExit(main())
