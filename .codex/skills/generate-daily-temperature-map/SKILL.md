---
name: generate-daily-temperature-map
description: Download the daily AEMET maximum-temperature maps and composite their exact, unmodified colors and provincial boundaries onto this Meteo project's fixed 3D Spain map, saving the final dated PNG under data/generated/YYYY-MM-DD. Use for the daily thermal-map run or when regenerating a specific date.
---

# Generate Daily Temperature Map

Run this workflow from the Meteo repository root. The requested date defaults to today's date in `Europe/Madrid`; accept an explicit ISO date when the user provides one.

## Fixed inputs and output

- Immutable visual base: `(Material de archivo)/bg/TEMPERATURAS.png`
- Peninsula and Balearic source: `data/raw/YYYY-MM-DD/temperaturas_maximas.png`
- Canary source: `data/raw/YYYY-MM-DD/temperaturas_maximas_canarias.png`
- Final deliverable: `data/generated/YYYY-MM-DD/temperaturas_final.png`

Never modify or overwrite the immutable visual base.

## Workflow

1. Resolve the run date and create no output for a different date.
2. Run `python scripts/generate_daily.py --date YYYY-MM-DD`. This downloads the current AEMET data and both maximum-temperature map images, keeps the originals in `data/raw/YYYY-MM-DD/`, and copies the downloaded maps into the matching generated folder.
3. Confirm that the base and both dated PNG sources exist, are non-empty, and can be opened. Never substitute a previous day's maps. If downloading or validation fails, stop without overwriting a final image and report the exact missing or failed input.
4. Load all three images with the image-viewing tool, then use the built-in image editing tool with all three filesystem paths:
   - Image 1 is the immutable edit target.
   - Image 2 supplies the exact peninsula and Balearic maximum-temperature pixels and provincial boundaries.
   - Image 3 supplies the exact Canary maximum-temperature pixels.
5. Apply the compositing specification below in one pass. Treat the AEMET images as authoritative pixel and color data, not as visual inspiration. Generate one final image unless the user explicitly requests variants. Do not run a cleanup pass that removes the source provincial boundaries.
6. Copy the selected generated PNG into the dated deliverable path. Creating or replacing `temperaturas_final.png` for the requested date is authorized by this workflow; never overwrite unrelated files.
7. Open the copied deliverable and verify its visual integrity. Confirm the title is unchanged, the colored field is confined to land top faces, all 3D geometry and cyan borders remain present, and the fine provincial boundaries from the AEMET peninsula source remain clearly visible above the temperature field. Compare multiple hot, mild, and cool areas against both dated AEMET sources and reject the output if any hue, saturation, brightness, palette band, transition, or geographic color distribution was invented or materially changed. Confirm that no AEMET legend, scale, logo, watermark, labels, gray source background, France, or North Africa were imported.
8. Report the absolute final path and whether the run used freshly downloaded inputs. A run is not complete until the dated final PNG exists and passes visual inspection.

## Compositing specification

Use case: compositing. Asset type: final 16:9 weather-map graphic.

Replace only the gray material on the top-facing land surfaces of the 3D map with the geographically corresponding temperature colors. Warp the flat fields onto the existing perspective and retain the original material texture, highlights, shadows, and relief.

## Absolute AEMET color fidelity

The dated AEMET images are the sole authority for every temperature color. Transfer their actual temperature-field pixels; never reinterpret, approximate, enhance, stylize, or regenerate the palette.

- Permit only geometric operations needed for placement: crop, mask, scale, perspective warp, and ordinary resampling.
- Preserve the original AEMET hues, saturation, brightness, contrast, palette bands, local transitions, hot/cool regions, and geographic distribution.
- Do not apply color grading, relighting, tinting, white-balance changes, gamma changes, saturation boosts, contrast boosts, palette substitution, smoothing, invented gradients, or artistic blending to the temperature layer.
- Do not create new colors between source palette bands or extend a hot/cool area beyond what the dated sources show.
- Preserve the 3D form with the base geometry, edges, extrusion, and existing scene shadows; do not recolor the temperature pixels to simulate lighting. If visual blending conflicts with source color fidelity, source color fidelity wins.

## Geographic registration invariants

Warp the mainland temperature field as one coherent raster after aligning the complete Spanish land outline. Do not relocate or regenerate individual hot or cool regions independently.

- Keep the Pyrenean band attached to Spain's extreme northern border with France, running through the Pyrenean parts of Navarra, northern Huesca, northern Lleida, and Girona. Never displace it into central or southern Aragon, Valencia, Castilla-La Mancha, Extremadura, Andalusia, Baleares, or Canarias.
- Use Galicia, the Cantabrian coast, the Mediterranean coast, Andalusia, and the Spain-Portugal border as additional registration anchors before applying the perspective warp.
- Transfer the peninsula and Balearic field only from the peninsula source. Transfer the Canary field only from the Canary source; never exchange or reuse temperature regions between these two sources.
- If any geographic feature does not align after a single coherent warp, reject the result instead of moving that feature separately.

Preserve the base image exactly outside those top-facing surfaces, including:

- canvas, framing, camera, perspective, map position, and size
- coastlines and all internal boundary lines
- 3D relief, extrusion, dark vertical sides, shadows, and reflections
- mainland, Balearic, and Canary island geometry and placement
- cyan glowing borders and highlights
- blue background, sun/glow, haze, lighting, and reflections
- the existing large 3D title `temperaturas`, with identical spelling, typography, position, and appearance

Keep the original cyan coastlines and internal borders above the temperature layer. Also retain the fine provincial boundary outlines from the AEMET peninsula source, accurately warped onto the 3D top surface and visible in their original source colors above the temperature field. These provincial lines are a required part of the final design, not artifacts, and must never be removed during refinement. Use the peninsula source for mainland Spain and Baleares, and the Canary source for the Canary Islands. Do not invent gradients or import any source-map element except the required provincial boundary lines: exclude the frame, legend, color scale, numbers, labels, logos, watermarks, copyright text, France, North Africa, and gray background. Do not color extruded sides, water, background, title, borders, shadows, or glow.

## Failure boundaries

- Do not fall back to a stale dated source.
- Do not accept an output that changes, invents, intensifies, dulls, smooths, or redistributes any AEMET temperature color.
- Reject an output whose Pyrenean cool band is not directly adjacent to the northern border with France in Navarra, Huesca, Lleida, and Girona.
- Do not remove, fade, recolor, or simplify the provincial boundary lines supplied by the peninsula source.
- Do not claim success if the image-generation tool returns no local PNG path.
- Do not overwrite an existing good deliverable with a failed or visibly corrupted result.
- If the built-in image tool is unavailable, stop and report that blocker; do not silently switch to another image model or API path.
