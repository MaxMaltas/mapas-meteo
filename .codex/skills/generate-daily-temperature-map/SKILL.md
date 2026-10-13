---
name: generate-daily-temperature-map
description: Download the daily AEMET maximum-temperature maps, build the project's registered temperature texture, and composite it onto the fixed 3D Spain map while preserving only the autonomous-community contours already present in the base. Use for the daily thermal-map run or when regenerating a specific date. Never use the raw AEMET graphics directly as image-model references.
---

# Generate Daily Temperature Map

Run this workflow from the Meteo repository root. The requested date defaults to today's date in `Europe/Madrid`; accept an explicit ISO date when the user provides one.

## Fixed inputs and output

- Immutable visual base: `(Material de archivo)/bg/TEMPERATURAS.png`
- Raw audit sources: `data/raw/YYYY-MM-DD/temperaturas_maximas.png` and `data/raw/YYYY-MM-DD/temperaturas_maximas_canarias.png`
- Authoritative registered source: `temperature_template/assets/daily/YYYY-MM-DD/temperatura_rellenada.png`
- Dated audit copy used for compositing: `data/generated/YYYY-MM-DD/temperatura_rellenada.png`
- Final deliverable for the current production AEP: `data/generated/YYYY-MM-DD/temperaturas_final.png` at exactly `1672 x 941`

Never modify or overwrite the immutable visual base.

## Workflow

1. Resolve the run date in `Europe/Madrid` and create no output for a different date.
2. Run `python scripts/generate_daily.py --date YYYY-MM-DD` to download fresh data. Use `--reuse-raw` only when rebuilding the same date from its already downloaded raw sources. Never substitute another day's maps.
3. Run `powershell -ExecutionPolicy Bypass -File scripts/update_temperature_template.ps1 -Stage Prepare -Date YYYY-MM-DD -NoLaunch`. This creates and validates the registered textures and copies them into `data/generated/YYYY-MM-DD/`.
4. Inspect `temperature_template/validation/registration_YYYY-MM-DD.json`. Require the matching date, at least `99 %` land coverage, and exactly `0` invented colours. Stop before compositing if any condition fails.
5. Load exactly two image references for the built-in image editing tool:
   - Image 1: the immutable 3D visual base.
   - Image 2: `data/generated/YYYY-MM-DD/temperatura_rellenada.png`, the sole authority for all temperatures, mainland and islands. It contains no boundary layer intended for final rendering.
6. Apply the compositing specification below in one pass and as one coherent geographic warp. Do not use either raw AEMET screenshot as an image-model reference.
7. Reject any candidate that adds provincial lines or additional autonomous-community outlines. Preserve the original autonomous-community contours already present in the 3D base exactly once.
8. Before replacing an existing good final, save a dated backup. Copy only a visually approved candidate to `data/generated/YYYY-MM-DD/temperaturas_final.png`.
9. Confirm the final is exactly `1672 x 941`, inspect it visually, then run `powershell -ExecutionPolicy Bypass -File scripts/run_daily.ps1 -Stage Apply -Date YYYY-MM-DD -NoLaunch` for the production preflight.
10. Report the absolute path, whether the inputs were freshly downloaded or reused for that date, and the measured coverage. A run is incomplete until the final exists and all checks pass.

Do not run the full `1920 x 1080` template publisher as a substitute for steps 5-9 while `METEO FINAL.aep` still expects the legacy `1672 x 941` composite.

## Compositing specification

Use case: compositing. Asset type: final 16:9 weather-map graphic.

Replace only the gray material on the top-facing land surfaces of the 3D map with the geographically corresponding registered temperature texture. Warp the complete texture as one raster onto the existing perspective and retain the original material texture, highlights, shadows, relief and cyan edge treatment.

### Thermal fidelity

`temperatura_rellenada.png` is the sole authority for every temperature colour used by the image model.

- Permit only the geometric operations needed for placement: crop, mask, scale, perspective warp and ordinary resampling.
- Preserve its hues, saturation, brightness, contrast, palette bands, local transitions and geographic distribution.
- Do not colour-grade, relight, tint, smooth, reinterpret, enhance or regenerate the palette.
- Do not create new gradients, move individual hot or cool regions, or extend regions beyond the registered source.
- Preserve the base 3D form with its geometry, extrusion and existing scene shadows. If visual blending conflicts with source fidelity, source fidelity wins.

### Geographic registration

Warp the full mainland temperature field as one coherent raster after aligning the complete Spanish land outline.

- Keep the Pyrenean cool band attached to Spain's northern border through Navarra, Huesca, Lleida and Girona.
- Use Galicia, the Cantabrian coast, the Mediterranean coast, Andalusia and the Spain-Portugal border as additional anchors.
- Keep the central cool zones aligned with their registered positions, including northern Madrid.
- The registered source already contains Baleares and Canarias in their correct design positions. Do not derive or reposition them from the raw AEMET screenshots.
- If alignment fails after one coherent warp, reject the result instead of repairing regions separately.

### Boundary policy

The final result must show no provincial boundary lines. Preserve only the autonomous-community contours, coastlines and cyan edge treatment already present in the immutable 3D base.

- Do not render `provincias.png`, `comunidades.png`, `provincias_sin_duplicados.png` or `temperatura_con_limites.png` over the final map.
- Do not add, redraw, strengthen, recolour or duplicate autonomous-community outlines.
- Do not erase, cover or weaken the autonomous-community separators already present in the base.
- Registration layers may be used invisibly by the preparation scripts, but they are not final visual content.

### Base invariants

Preserve the base image exactly outside the top-facing land surfaces, including:

- canvas, framing, camera, perspective, map position and size
- coastlines, 3D relief, extrusion, dark vertical sides, shadows and reflections
- mainland, Balearic and Canary island geometry and placement
- cyan glowing borders and highlights
- blue background, sun/glow, haze, lighting and reflections
- the existing large 3D title `temperaturas`, with identical spelling, typography, position and appearance

Do not import the AEMET frame, legend, scale, numbers, labels, logos, watermark, copyright text, gray background, France or North Africa. Do not colour extruded sides, water, background, title, shadows or glow.

## Failure boundaries

- Use `temperatura_rellenada.png` as the only final image-model temperature reference.
- Never use either raw AEMET screenshot directly as an image-model reference.
- Never fall back to a stale dated source.
- Reject any output that changes or redistributes the registered temperature colours.
- Reject any output whose Pyrenean cool band or temperature regions are geographically displaced.
- Reject any output with visible provincial lines, added or doubled autonomous-community outlines, or missing original autonomous-community separators.
- Do not claim success if the image-generation tool returns no local PNG path.
- Do not overwrite an existing good deliverable with a failed or visibly corrupted result.
- If the built-in image tool is unavailable, stop and report that blocker; do not silently switch to another image model or API path.
