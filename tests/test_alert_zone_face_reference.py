import hashlib
import json
import unittest
from collections import Counter
from pathlib import Path

from meteo_pipeline.alert_map import _planar_faces, read_alert_shape


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "data" / "alert_map_template" / "DOMDocument.xml"
REFERENCE = ROOT / "config" / "alert_zone_faces.reference.json"


class AlertZoneFaceReferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.document = json.loads(REFERENCE.read_text(encoding="utf-8"))
        cls.assignments = cls.document["assignments"]

    def test_reference_matches_current_template(self) -> None:
        faces = _planar_faces(read_alert_shape(TEMPLATE, "Capa_4"))
        self.assertEqual(len(faces), 200)
        self.assertEqual(len(self.assignments), len(faces))
        self.assertEqual(
            self.document["template_sha256"], hashlib.sha256(TEMPLATE.read_bytes()).hexdigest()
        )

    def test_every_face_and_land_polygon_part_is_identified_once(self) -> None:
        self.assertEqual(
            sorted(item["face"] for item in self.assignments), list(range(200))
        )
        counts = Counter(item["zone_code"] for item in self.assignments)
        self.assertEqual(len(counts), 182)
        self.assertEqual(sum(counts.values()), 200)
        self.assertFalse(any(code.endswith("C") for code in counts))

    def test_all_marine_zones_remain_independent(self) -> None:
        marine = self.document["marine_zones"]
        self.assertEqual(self.document["marine_zone_count"], 51)
        self.assertEqual(self.document["marine_polygon_part_count"], 51)
        self.assertEqual(len(marine), 51)
        self.assertTrue(all(item["zone_code"].endswith("C") for item in marine))
        self.assertEqual(len({item["zone_code"] for item in marine}), 51)
        self.assertIn("610403C", {item["zone_code"] for item in marine})
        self.assertIn("733005C", {item["zone_code"] for item in marine})
        self.assertIn("770301C", {item["zone_code"] for item in marine})

    def test_known_problem_areas_have_stable_faces(self) -> None:
        lookup = {
            (item["zone_code"], item["part"]): item["face"]
            for item in self.assignments
        }
        self.assertEqual(lookup[("645401", 0)], 25)  # Sierra Tramontana
        self.assertEqual(lookup[("645404", 0)], 22)  # Sur de Mallorca
        self.assertEqual(lookup[("770301", 0)], 159)  # Litoral norte de Alicante
        self.assertEqual(lookup[("733005", 0)], 174)  # Campo de Cartagena
        self.assertEqual(lookup[("610403", 0)], 169)  # Poniente y Almería


if __name__ == "__main__":
    unittest.main()
