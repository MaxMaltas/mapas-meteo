import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from meteo_pipeline.alert_map import (
    _planar_faces,
    read_alert_shape,
    render_alert_map,
)


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "data" / "alert_map_template" / "DOMDocument.xml"
REFERENCE = ROOT / "config" / "alert_zone_faces.reference.json"


class AlertMapTests(unittest.TestCase):
    def test_reads_original_animate_layers(self) -> None:
        self.assertGreater(len(read_alert_shape(TEMPLATE, "Capa_4")), 1000)
        self.assertGreater(len(read_alert_shape(TEMPLATE, "linea_sobre", frame=5)), 500)

    def test_renders_transparent_full_hd_png(self) -> None:
        output = ROOT / "output" / "test_alertas.png"
        try:
            render_alert_map(TEMPLATE, [], output)
            with Image.open(output) as image:
                self.assertEqual(image.size, (1920, 1080))
                self.assertEqual(image.mode, "RGBA")
                self.assertEqual(image.getpixel((0, 0))[3], 0)
                colors = image.convert("RGB").getcolors(maxcolors=10_000_000)
                self.assertIsNotNone(colors)
                self.assertIn((0, 204, 102), [color for _, color in colors or []])
        finally:
            output.unlink(missing_ok=True)

    def test_fixed_reference_assigns_mallorca_levels_to_correct_faces(self) -> None:
        output = ROOT / "output" / "test_alertas_reference.png"
        zones = [
            {"code": "645401", "level": "yellow", "polygons": []},
            {"code": "645404", "level": "orange", "polygons": []},
        ]
        try:
            render_alert_map(TEMPLATE, zones, output, zone_reference=REFERENCE)
            faces = _planar_faces(read_alert_shape(TEMPLATE, "Capa_4"))
            with Image.open(output).convert("RGB") as image:
                self.assertGreater(
                    self._face_color_pixels(image, faces[25], (254, 255, 2)), 100
                )
                self.assertGreater(
                    self._face_color_pixels(image, faces[22], (231, 113, 29)), 100
                )
        finally:
            output.unlink(missing_ok=True)

    @staticmethod
    def _face_color_pixels(image: Image.Image, polygon, color: tuple[int, int, int]) -> int:
        mask = Image.new("1", image.size)
        ImageDraw.Draw(mask).polygon(polygon, fill=1)
        return sum(
            1
            for pixel, selected in zip(
                image.get_flattened_data(), mask.get_flattened_data()
            )
            if selected and pixel == color
        )

    def test_fixed_reference_renders_marine_warning_as_independent_zone(self) -> None:
        output = ROOT / "output" / "test_alertas_marine.png"
        zones = [{"code": "711501C", "level": "yellow", "polygons": []}]
        try:
            render_alert_map(TEMPLATE, zones, output, zone_reference=REFERENCE)
            with Image.open(output).convert("RGB") as image:
                colors = {
                    color: count
                    for count, color in image.getcolors(maxcolors=10_000_000) or []
                }
                self.assertGreater(colors.get((254, 255, 2), 0), 100)
        finally:
            output.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
