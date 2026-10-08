from __future__ import annotations

import argparse
import html
import json
import sys
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from meteo_pipeline.alert_map import _planar_faces, read_alert_shape  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--reference",
        type=Path,
        default=ROOT / "config" / "alert_zone_faces.reference.json",
    )
    parser.add_argument(
        "--template",
        type=Path,
        default=ROOT / "data" / "alert_map_template" / "DOMDocument.xml",
    )
    args = parser.parse_args()

    document = json.loads(args.reference.read_text(encoding="utf-8"))
    assignments = {item["face"]: item for item in document["assignments"]}
    faces = _planar_faces(read_alert_shape(args.template, "Capa_4"))
    zones: dict[str, dict] = defaultdict(lambda: {"faces": [], "parts": []})

    paths = []
    for face_index, polygon in enumerate(faces):
        item = assignments[face_index]
        code = item["zone_code"]
        zones[code]["name"] = item["zone_name"]
        zones[code]["faces"].append(face_index)
        zones[code]["parts"].append(item["part"])
        commands = " ".join(
            ("M" if index == 0 else "L") + f"{x:.2f},{y:.2f}"
            for index, (x, y) in enumerate(polygon)
        )
        title = html.escape(
            f"{code} — {item['zone_name']} · cara {face_index} · fragmento {item['part']}"
        )
        paths.append(
            f'<path data-code="{code}" data-face="{face_index}" '
            f'data-part="{item["part"]}" d="{commands} Z"><title>{title}</title></path>'
        )

    zone_rows = [
        {
            "code": code,
            "name": value["name"],
            "faces": value["faces"],
            "parts": value["parts"],
        }
        for code, value in sorted(zones.items())
    ]
    options = "\n".join(
        f'<option value="{row["code"]}">{row["code"]} — {html.escape(row["name"])}</option>'
        for row in zone_rows
    )
    zone_json = json.dumps(zone_rows, ensure_ascii=False, separators=(",", ":"))

    fragment = f'''<div id="alert-zone-inventory">
  <h2>Inventario de zonas del mapa Animate</h2>
  <div class="viz-controls">
    <label class="form-label" for="alert-zone-select">Zona terrestre AEMET
      <select class="form-select" id="alert-zone-select">
        {options}
      </select>
    </label>
  </div>
  <svg viewBox="180 0 1510 1070" role="img" aria-labelledby="alert-zone-title alert-zone-desc">
    <title id="alert-zone-title">Correspondencia entre las caras del mapa Animate y las zonas terrestres AEMET</title>
    <desc id="alert-zone-desc">Mapa interactivo con 200 caras correspondientes a 182 zonas terrestres. Seleccione una zona para resaltarla.</desc>
    <g class="zone-faces">
      {''.join(paths)}
    </g>
    <g class="selected-label" aria-hidden="true">
      <circle r="5"></circle>
      <text></text>
    </g>
  </svg>
  <div class="card text-small" id="alert-zone-detail" aria-live="polite"></div>
</div>
<style>
  #alert-zone-inventory {{ display: grid; gap: 12px; }}
  #alert-zone-inventory .viz-controls {{ align-items: end; }}
  #alert-zone-inventory .form-label {{ min-width: min(100%, 360px); }}
  #alert-zone-inventory svg {{ width: 100%; height: auto; display: block; }}
  #alert-zone-inventory .zone-faces path {{ fill: color-mix(in srgb, var(--muted) 72%, transparent); stroke: var(--border); stroke-width: 1.2; vector-effect: non-scaling-stroke; }}
  #alert-zone-inventory .zone-faces path.is-selected {{ fill: color-mix(in srgb, var(--viz-series-1) 70%, transparent); stroke: var(--foreground); stroke-width: 2.4; }}
  #alert-zone-inventory .selected-label {{ pointer-events: none; }}
  #alert-zone-inventory .selected-label circle {{ fill: var(--foreground); }}
  #alert-zone-inventory .selected-label text {{ fill: var(--foreground); font-size: 18px; font-weight: 500; paint-order: stroke; stroke: var(--background); stroke-width: 4px; }}
</style>
<script>
(() => {{
  const root = document.getElementById('alert-zone-inventory');
  const select = root.querySelector('#alert-zone-select');
  const detail = root.querySelector('#alert-zone-detail');
  const label = root.querySelector('.selected-label');
  const zones = {zone_json};
  const byCode = new Map(zones.map(zone => [zone.code, zone]));
  const saved = window.openai && window.openai.widgetState && window.openai.widgetState.privateContent;
  select.value = saved && byCode.has(saved.zoneCode) ? saved.zoneCode : '645404';

  function update() {{
    const zone = byCode.get(select.value) || zones[0];
    const selectedPaths = [];
    root.querySelectorAll('.zone-faces path').forEach(path => {{
      const active = path.dataset.code === zone.code;
      path.classList.toggle('is-selected', active);
      if (active) selectedPaths.push(path);
    }});
    const boxes = selectedPaths.map(path => path.getBBox());
    const left = Math.min(...boxes.map(box => box.x));
    const top = Math.min(...boxes.map(box => box.y));
    const right = Math.max(...boxes.map(box => box.x + box.width));
    const bottom = Math.max(...boxes.map(box => box.y + box.height));
    const x = (left + right) / 2;
    const y = (top + bottom) / 2;
    label.setAttribute('transform', `translate(${{x}} ${{y}})`);
    label.querySelector('text').setAttribute('x', '9');
    label.querySelector('text').setAttribute('y', '-9');
    label.querySelector('text').textContent = zone.code;
    detail.textContent = `${{zone.code}} — ${{zone.name}} · cara${{zone.faces.length === 1 ? '' : 's'}} ${{zone.faces.join(', ')}} · ${{zone.faces.length}} fragmento${{zone.faces.length === 1 ? '' : 's'}}`;
    if (window.openai && window.openai.setWidgetState) {{
      window.openai.setWidgetState({{ modelContent: {{ zoneCode: zone.code, zoneName: zone.name, faces: zone.faces }}, privateContent: {{ zoneCode: zone.code }} }}).catch(() => {{}});
    }}
  }}
  select.addEventListener('change', update);
  root.querySelectorAll('.zone-faces path').forEach(path => path.addEventListener('click', () => {{ select.value = path.dataset.code; update(); }}));
  update();
}})();
</script>
'''
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(fragment, encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
