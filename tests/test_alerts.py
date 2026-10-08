import io
import tarfile
import unittest
from datetime import date, datetime

from meteo_pipeline.alerts import summarise_cap_by_province, summarise_cap_by_zone


CAP_XML = b'''<?xml version="1.0" encoding="UTF-8"?>
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <info>
    <event>Aviso de lluvias de nivel naranja</event>
    <severity>Severe</severity>
    <onset>2026-09-25T10:00:00+02:00</onset>
    <expires>2026-09-25T20:00:00+02:00</expires>
    <area>
      <areaDesc>Valle del Guadalquivir de Jaen</areaDesc>
      <polygon>38.1,-3.8 38.2,-3.7 38.0,-3.6 38.1,-3.8</polygon>
      <geocode>
        <valueName>AEMET-Meteoalerta zona</valueName>
        <value>612303</value>
      </geocode>
    </area>
  </info>
</alert>'''


def make_tar(payload: bytes = CAP_XML) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        info = tarfile.TarInfo("warning.xml")
        info.size = len(payload)
        archive.addfile(info, io.BytesIO(payload))
    return buffer.getvalue()


class AlertTests(unittest.TestCase):
    def test_uses_maximum_level_for_province(self) -> None:
        summary = summarise_cap_by_province(make_tar(), date(2026, 9, 25))
        jaen = next(item for item in summary["provinces"] if item["code"] == "23")
        self.assertEqual(jaen["level"], "orange")
        self.assertEqual(jaen["alerts"][0]["area"], "Valle del Guadalquivir de Jaen")

    def test_includes_zone_polygon_for_renderer(self) -> None:
        summary = summarise_cap_by_zone(make_tar(), date(2026, 9, 25))
        self.assertEqual(len(summary["zones"]), 1)
        zone = summary["zones"][0]
        self.assertEqual(zone["code"], "612303")
        self.assertEqual(zone["level"], "orange")
        self.assertEqual(zone["polygons"][0][0], [38.1, -3.8])

    def test_preserves_marine_zone_suffix(self) -> None:
        payload = CAP_XML.replace(b"612303", b"612303C").replace(
            b"Valle del Guadalquivir de Jaen", b"Costa - Jaen"
        )
        summary = summarise_cap_by_zone(make_tar(payload), date(2026, 9, 25))
        self.assertEqual(summary["zones"][0]["code"], "612303C")

    def test_as_of_excludes_expired_warning_but_keeps_daily_summary(self) -> None:
        payload = make_tar()
        cutoff = datetime.fromisoformat("2026-09-25T21:00:00+02:00")
        self.assertEqual(
            summarise_cap_by_zone(payload, date(2026, 9, 25))["zones"][0]["level"],
            "orange",
        )
        self.assertEqual(
            summarise_cap_by_zone(payload, date(2026, 9, 25), as_of=cutoff)["zones"],
            [],
        )
        jaen = next(
            item for item in summarise_cap_by_province(payload, date(2026, 9, 25), as_of=cutoff)["provinces"]
            if item["code"] == "23"
        )
        self.assertEqual(jaen["level"], "green")

    def test_as_of_keeps_warning_later_in_same_day(self) -> None:
        cutoff = datetime.fromisoformat("2026-09-25T08:00:00+02:00")
        summary = summarise_cap_by_zone(make_tar(), date(2026, 9, 25), as_of=cutoff)
        self.assertEqual(summary["zones"][0]["level"], "orange")


if __name__ == "__main__":
    unittest.main()
