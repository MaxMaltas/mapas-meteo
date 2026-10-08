---
name: generate-daily-alert-map
description: Download daily AEMET CAP warnings, render their exact categorical zone colors, and composite that alert layer onto this Meteo project's fixed 3D alert map, saving a dated alertas_final.png. Use for the daily alert-map run or when regenerating alerts for a specific date; do not use for temperature maps.
---

# Generate Daily Alert Map

Run this workflow from the Meteo repository root. The requested date defaults to today's date in `Europe/Madrid`; accept an explicit ISO date when the user provides one.

This workflow is intentionally separate from `$generate-daily-temperature-map`: alerts use CAP warning polygons and categorical colors, while temperatures use continuous raster fields.

## Fixed inputs and output

- Immutable 3D base: `(Material de archivo)/bg/ALERTAS.png`
- Daily authoritative alert layer: `data/generated/YYYY-MM-DD/alertas.png`
- Finish reference only: `(Material de archivo)/MATERIAL/ChatGPT Image 24 sept 2026, 11_40_12.png`
- Final deliverable: `data/generated/YYYY-MM-DD/alertas_final.png`
- Daily metadata and audit source: `data/generated/YYYY-MM-DD/meteo.json`

Never modify or overwrite the immutable 3D base, the finish reference, or the daily technical `alertas.png` layer.

## Workflow

1. Resolve the run date and create no output for a different date.
2. Run `python scripts/generate_daily.py --date YYYY-MM-DD`. The existing pipeline downloads AEMET data, processes the active CAP warning zones, and renders `data/generated/YYYY-MM-DD/alertas.png` from the vector template.
3. Confirm that the immutable base, dated `alertas.png`, finish reference, and dated `meteo.json` exist and are non-empty. Open all three images. Never substitute alert data from a previous date.
4. Read `meteo.json` only to validate the dated alert state. The PNG `alertas.png` remains the visual authority for zone geometry, outlines, colors, and placement.
5. Use the built-in image editing tool with these roles:
   - Image 1: immutable edit target, `ALERTAS.png`.
   - Image 2: authoritative daily insert, dated `alertas.png`.
   - Image 3: finish reference for the desired integration quality only.
6. Apply the compositing specification below in one pass. Generate one final image unless the user explicitly requests variants.
7. Copy the selected generated PNG to `data/generated/YYYY-MM-DD/alertas_final.png`. Replacing that exact dated deliverable is authorized by this workflow; never overwrite unrelated files.
8. Open the copied deliverable and verify the title, scene invariants, categorical colors, zone placement, outlines, islands, and absence of imported backgrounds or labels. A run is not complete until the final dated PNG exists and passes visual inspection.
9. Report the absolute final path and whether fresh CAP data was used.

## Alert data authority

The dated technical `alertas.png` is the sole authority for the day's alert state. Treat its pixels as data, not inspiration.

- Preserve every warning-zone boundary and the exact set, shape, position, and count of non-green zones.
- Preserve the exact categorical palette produced by the renderer:
  - green/no active warning: `#00CC66`
  - yellow warning: `#FEFF02`
  - orange warning: `#E7711D`
  - red warning: `#CC0000`
- Permit only crop, mask, scale, perspective warp, and ordinary resampling needed to fit the daily layer onto the 3D top surfaces.
- Do not recolor, color-grade, relight, tint, change saturation or brightness, smooth zone edges, invent gradients, merge zones, split zones, or fabricate warnings.
- Never copy alert locations or colors from the finish reference. It demonstrates only the desired finished 3D appearance and may represent a different date.
- If visual blending conflicts with alert-data fidelity, the dated `alertas.png` wins.

## Compositing specification

Use case: compositing. Asset type: final 16:9 weather alert graphic.

Replace only the gray material on the top-facing land surfaces of the 3D map in `ALERTAS.png` with the daily alert layer. Warp the flat alert artwork accurately onto the existing perspective. Preserve the alert layer's internal zone outlines and all of its categorical fills. The transparent parts of the source layer are not content and must not appear as black or gray.

Preserve the base exactly outside those top-facing surfaces, including:

- canvas, framing, camera, perspective, map position, and size
- exact coastline and original thicker internal boundary network
- 3D relief, extrusion, dark vertical sides, shadows, and reflections
- mainland, Balearic, and Canary island geometry and placement
- cyan glowing coastlines, borders, and highlights
- blue background, sun/glow, haze, lighting, and reflections
- the existing large 3D title `alertas`, with identical spelling, typography, position, and appearance

Keep the original cyan/white borders from the base above the alert layer. Keep the daily alert zone outlines visible as in the technical source and the finish reference. Apply alert colors only to upper land faces; never color the vertical extruded sides, water/background, title, glow, shadows, or reflections.

Do not import the transparent-source preview background, frame, labels, legend, numbers, logos, watermarks, copyright text, or any extra object. Do not add a color key unless the user explicitly requests one.

## Validation and failure boundaries

- Compare all yellow, orange, and red zones in the final image against the dated technical `alertas.png`; they must match geographically and categorically.
- Confirm that green areas remain green and that no unalerted zone acquired a warning color.
- Confirm that all islands present in the daily layer are represented without changing their 3D geometry.
- Do not use stale CAP data or the finish reference as alert data.
- Do not accept an output with invented, missing, shifted, merged, recolored, or softened alert zones.
- Do not overwrite an existing good deliverable with a failed or visibly corrupted result.
- If the built-in image tool is unavailable, stop and report that blocker; do not silently switch to another image model or API path.
