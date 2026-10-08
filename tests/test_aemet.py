import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from meteo_pipeline.aemet import (
    AemetClient,
    AemetError,
    TEMPERATURE_MAXIMA_CANARY_PAGE_URL,
    save_image_download,
)


PNG = b"\x89PNG\r\n\x1a\n" + b"test image"


class AemetImageTests(unittest.TestCase):
    def test_discovers_and_downloads_temperature_maxima_map(self) -> None:
        page = b'''<html><img
            src="/imagenes_d/eltiempo/prediccion/temperaturas/mapa.png"
            alt="Temperaturas m\xe1ximas"></html>'''
        client = AemetClient("test-key", retries=0)
        client._request = Mock(
            side_effect=[(page, "text/html"), (PNG, "image/png")]
        )

        download = client.download_temperature_maxima_map()

        self.assertEqual(
            download.image_url,
            "https://www.aemet.es/imagenes_d/eltiempo/prediccion/temperaturas/mapa.png",
        )
        self.assertEqual(download.payload, PNG)
        image_request = client._request.call_args_list[1].args[0]
        self.assertEqual(image_request.headers["Accept"], "image/*")

    def test_rejects_response_that_is_not_an_image(self) -> None:
        page = b'''<img
            src="/imagenes_d/eltiempo/prediccion/temperaturas/mapa.png"
            alt="Temperaturas m\xe1ximas">'''
        client = AemetClient("test-key", retries=0)
        client._request = Mock(
            side_effect=[(page, "text/html"), (b"error", "text/html")]
        )

        with self.assertRaisesRegex(AemetError, "imagen reconocible"):
            client.download_temperature_maxima_map()

    def test_accepts_canary_islands_page(self) -> None:
        page = b'''<img
            src="/imagenes_d/eltiempo/prediccion/temperaturas/canarias.png"
            alt="Temperaturas m\xe1ximas">'''
        client = AemetClient("test-key", retries=0)
        client._request = Mock(
            side_effect=[(page, "text/html"), (PNG, "image/png")]
        )

        download = client.download_temperature_maxima_map(
            TEMPERATURE_MAXIMA_CANARY_PAGE_URL
        )

        page_request = client._request.call_args_list[0].args[0]
        self.assertEqual(page_request.full_url, TEMPERATURE_MAXIMA_CANARY_PAGE_URL)
        self.assertEqual(
            download.image_url,
            "https://www.aemet.es/imagenes_d/eltiempo/prediccion/temperaturas/canarias.png",
        )

    def test_saves_image_with_detected_extension(self) -> None:
        client = AemetClient("test-key", retries=0)
        page = b'''<img
            src="/imagenes_d/eltiempo/prediccion/temperaturas/mapa.png"
            alt="Temperaturas m\xe1ximas">'''
        client._request = Mock(
            side_effect=[(page, "text/html"), (PNG, "image/png")]
        )
        download = client.download_temperature_maxima_map()

        directory = Path("mapas")
        with (
            patch.object(Path, "mkdir") as mkdir,
            patch.object(Path, "write_bytes") as write_bytes,
        ):
            path = save_image_download(download, directory, "temperaturas_maximas")

        self.assertEqual(path, Path("mapas/temperaturas_maximas.png"))
        mkdir.assert_called_once_with(parents=True, exist_ok=True)
        write_bytes.assert_called_once_with(PNG)


if __name__ == "__main__":
    unittest.main()
