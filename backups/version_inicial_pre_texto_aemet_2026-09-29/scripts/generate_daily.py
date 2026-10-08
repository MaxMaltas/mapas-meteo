from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from meteo_pipeline.aemet import AemetClient, decode_json_payload, save_download
from meteo_pipeline.alerts import summarise_cap_by_province
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
        daily_payload = daily_download.payload
        hourly_payload = hourly_download.payload
        alerts_payload = alerts_download.payload

    document = build_daily_document(
        decode_json_payload(daily_payload),
        decode_json_payload(hourly_payload),
        config,
        args.date,
        str(alerts_path.relative_to(ROOT)).replace("\\", "/"),
        summarise_cap_by_province(alerts_payload, args.date),
    )

    output_dir = ROOT / "data" / "generated" / args.date.isoformat()
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "meteo.json"
    output_path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    latest_dir = ROOT / "data" / "generated" / "latest"
    latest_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(output_path, latest_dir / "meteo.json")

    print(output_path)
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


if __name__ == "__main__":
    raise SystemExit(main())
