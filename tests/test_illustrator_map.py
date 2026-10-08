import importlib.util
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "MAPA_ALERTAS_ILUSTRATOR.ai"
REFERENCE = ROOT / "config/alert_zone_faces.illustrator.reference.json"


@unittest.skipUnless(importlib.util.find_spec("pypdf"), "pypdf no instalado")
class IllustratorMapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from meteo_pipeline.illustrator_map import read_illustrator_shapes
        from meteo_pipeline.illustrator_alerts import load_reference

        cls.shapes = read_illustrator_shapes(SOURCE)
        cls.reference = load_reference(REFERENCE, SOURCE)

    def test_reads_current_source_layers(self):
        self.assertEqual(
            Counter(shape.layer for shape in self.shapes),
            {"MAR": 51, "ZONAS AEMET": 182, "PROVINCIAS": 66, "CCAA": 31},
        )
        self.assertEqual(len({shape.form_id for shape in self.shapes}), 330)

    def test_reference_covers_all_cap_codes(self):
        from tools.build_alert_zone_face_reference import _read_cap_snapshots

        cap = ROOT / self.reference["source_cap"]
        snapshots = _read_cap_snapshots(cap)
        zones = max(snapshots.values(), key=len)
        referenced = {zone["code"] for zone in self.reference["land_zones"] + self.reference["marine_zones"]}
        self.assertEqual(referenced, set(zones))
        self.assertEqual(len(self.reference["land_zones"]), 182)
        self.assertEqual(len(self.reference["marine_zones"]), 51)
        self.assertEqual(len(self.reference["province_outlines"]), 66)
        self.assertEqual(len(self.reference["community_outlines"]), 31)
        self.assertTrue(all(zone["province"] for zone in self.reference["land_zones"]))

    def test_grouped_and_corrected_land_zones(self):
        zones = {zone["code"]: zone for zone in self.reference["land_zones"]}
        self.assertEqual(zones["611801"]["name"], "Cuenca del Genil")
        self.assertEqual(zones["681902"]["name"], "Parameras de Molina")
        self.assertEqual(len(zones["645301"]["parts"]), 2)
        self.assertEqual(len(zones["659101"]["parts"]), 2)
        for code in ("690803", "690804", "691702", "691704"):
            self.assertTrue(zones[code]["parts"][0]["polygons"])

    def test_render_uses_distinct_codes(self):
        from PIL import Image
        from meteo_pipeline.illustrator_alerts import render_illustrator_alert_map

        warnings = [
            {"code": "611801", "level": "orange"},
            {"code": "611802", "level": "yellow"},
            {"code": "659001C", "level": "red"},
        ]
        output = ROOT / "output" / "test_illustrator_alerts.png"
        render_illustrator_alert_map(SOURCE, REFERENCE, warnings, output)
        image = Image.open(output).convert("RGBA")
        self.assertEqual(image.size, (1920, 1080))
        counts = dict((colour, count) for count, colour in image.getcolors(1920 * 1080))
        self.assertGreater(counts[(231, 113, 29, 255)], 1000)
        self.assertGreater(counts[(254, 255, 2, 255)], 1000)
        self.assertGreater(counts[(204, 0, 0, 255)], 100)
        self.assertGreater(counts[(192, 192, 192, 255)], 1000)  # Zonas de aviso
        self.assertGreater(counts[(128, 128, 128, 255)], 1000)  # Provincias
        self.assertGreater(counts[(0, 0, 0, 255)], 1000)  # Comunidades


if __name__ == "__main__":
    unittest.main()
