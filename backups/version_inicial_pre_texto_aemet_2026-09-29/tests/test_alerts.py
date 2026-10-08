import io
import tarfile
import unittest
from datetime import date

from meteo_pipeline.alerts import summarise_cap_by_province


CAP_XML = b'''<?xml version="1.0" encoding="UTF-8"?>
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <info>
    <event>Aviso de lluvias de nivel naranja</event>
    <severity>Severe</severity>
    <onset>2026-09-25T10:00:00+02:00</onset>
    <expires>2026-09-25T20:00:00+02:00</expires>
    <area>
      <areaDesc>Valle del Guadalquivir de Jaen</areaDesc>
      <geocode>
        <valueName>AEMET-Meteoalerta zona</valueName>
        <value>612303</value>
      </geocode>
    </area>
  </info>
</alert>'''


def make_tar() -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        info = tarfile.TarInfo("warning.xml")
        info.size = len(CAP_XML)
        archive.addfile(info, io.BytesIO(CAP_XML))
    return buffer.getvalue()


class AlertTests(unittest.TestCase):
    def test_uses_maximum_level_for_province(self) -> None:
        summary = summarise_cap_by_province(make_tar(), date(2026, 9, 25))
        jaen = next(item for item in summary["provinces"] if item["code"] == "23")
        self.assertEqual(jaen["level"], "orange")
        self.assertEqual(jaen["alerts"][0]["area"], "Valle del Guadalquivir de Jaen")


if __name__ == "__main__":
    unittest.main()
