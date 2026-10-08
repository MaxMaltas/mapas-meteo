from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extrae el XML vectorial reutilizable de MAPA_ALERTAS.fla."
    )
    parser.add_argument("--fla", type=Path, default=ROOT / "MAPA_ALERTAS.fla")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data" / "alert_map_template" / "DOMDocument.xml",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    completed = subprocess.run(
        ["tar", "-xOf", str(args.fla), "DOMDocument.xml"],
        check=True,
        stdout=subprocess.PIPE,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(completed.stdout)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
