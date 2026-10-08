from __future__ import annotations

import gzip
import io
import json
import tarfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


BASE_URL = "https://opendata.aemet.es/opendata"
TEMPERATURE_MAXIMA_PAGE_URL = (
    "https://www.aemet.es/es/eltiempo/prediccion/temperaturas"
    "?dia=&zona=penyb&img=maxima"
)
TEMPERATURE_MAXIMA_CANARY_PAGE_URL = (
    "https://www.aemet.es/es/eltiempo/prediccion/temperaturas"
    "?dia=hoy&zona=can&img=maxima"
)


class AemetError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProductDownload:
    endpoint: str
    envelope: dict[str, Any]
    payload: bytes
    content_type: str


@dataclass(frozen=True)
class ImageDownload:
    page_url: str
    image_url: str
    payload: bytes
    content_type: str


class _TemperatureMapParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.source: str | None = None

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag.casefold() != "img" or self.source:
            return
        attributes = dict(attrs)
        source = attributes.get("src") or ""
        alt = (attributes.get("alt") or "").casefold()
        if (
            "temperaturas máximas" in alt
            and "/eltiempo/prediccion/temperaturas/" in source
        ):
            self.source = source


class AemetClient:
    def __init__(self, api_key: str, timeout: int = 90, retries: int = 4) -> None:
        if not api_key:
            raise ValueError("Falta AEMET_API_KEY")
        self.api_key = api_key
        self.timeout = timeout
        self.retries = retries

    def _request(self, request: urllib.request.Request) -> tuple[bytes, str]:
        for attempt in range(self.retries + 1):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    return response.read(), response.headers.get_content_type()
            except urllib.error.HTTPError as error:
                retryable = error.code == 429 or 500 <= error.code < 600
                if not retryable or attempt == self.retries:
                    detail = error.read().decode("utf-8", errors="replace")
                    raise AemetError(f"AEMET respondió HTTP {error.code}: {detail}") from error
                retry_after = error.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else (
                    60 if error.code == 429 else min(2 ** attempt, 30)
                )
                time.sleep(delay)
            except urllib.error.URLError as error:
                if attempt == self.retries:
                    raise AemetError(f"No se pudo conectar con AEMET: {error}") from error
                time.sleep(min(2 ** attempt, 30))
        raise AssertionError("bucle de reintentos agotado")

    def download_product(self, endpoint: str) -> ProductDownload:
        endpoint = "/" + endpoint.lstrip("/")
        request = urllib.request.Request(
            BASE_URL + endpoint,
            headers={"accept": "application/json", "api_key": self.api_key},
        )
        raw_envelope, _ = self._request(request)
        try:
            envelope = json.loads(raw_envelope.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise AemetError("La respuesta inicial de AEMET no es JSON válido") from error

        if int(envelope.get("estado", 0)) != 200 or not envelope.get("datos"):
            raise AemetError(f"AEMET no devolvió datos: {envelope}")

        # La URL firmada de datos caduca aproximadamente a los cinco minutos.
        data_request = urllib.request.Request(envelope["datos"], headers={"accept": "*/*"})
        payload, content_type = self._request(data_request)
        return ProductDownload(endpoint, envelope, payload, content_type)

    def download_temperature_maxima_map(
        self, page_url: str = TEMPERATURE_MAXIMA_PAGE_URL
    ) -> ImageDownload:
        """Descarga un mapa público de temperaturas máximas de AEMET.

        OpenData no ofrece este gráfico como producto de la API. La URL del PNG
        cambia con cada elaboración, por lo que se obtiene de la página oficial.
        """
        page_request = urllib.request.Request(
            page_url,
            headers={
                "accept": "text/html,application/xhtml+xml",
                "user-agent": "MeteoPipeline/1.0 (+https://www.aemet.es/)",
            },
        )
        page_payload, _ = self._request(page_request)
        parser = _TemperatureMapParser()
        parser.feed(_decode_text(page_payload))
        if not parser.source:
            raise AemetError(
                "AEMET no publicó el mapa de temperaturas máximas en la página esperada"
            )

        image_url = urllib.parse.urljoin(page_url, parser.source)
        parsed_url = urllib.parse.urlsplit(image_url)
        if parsed_url.scheme != "https" or parsed_url.hostname not in {
            "aemet.es",
            "www.aemet.es",
        }:
            raise AemetError(
                f"La página de AEMET devolvió una imagen no válida: {image_url}"
            )

        image_request = urllib.request.Request(
            image_url,
            headers={
                "accept": "image/*",
                "referer": page_url,
                "user-agent": "MeteoPipeline/1.0 (+https://www.aemet.es/)",
            },
        )
        payload, content_type = self._request(image_request)
        _image_suffix(payload, content_type)
        return ImageDownload(page_url, image_url, payload, content_type)


def decode_json_payload(payload: bytes) -> Any:
    """Decodifica JSON directo o empaquetado como gzip, ZIP o TAR."""
    if payload.startswith(b"\x1f\x8b"):
        payload = gzip.decompress(payload)

    if payload.startswith(b"PK\x03\x04"):
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            documents = [
                _loads_json_bytes(archive.read(name))
                for name in archive.namelist()
                if name.lower().endswith(".json")
            ]
        return _merge_documents(documents)

    try:
        with tarfile.open(fileobj=io.BytesIO(payload), mode="r:*") as archive:
            documents = []
            for member in archive.getmembers():
                if member.isfile() and member.name.lower().endswith(".json"):
                    extracted = archive.extractfile(member)
                    if extracted:
                        documents.append(_loads_json_bytes(extracted.read()))
            if documents:
                return _merge_documents(documents)
    except tarfile.ReadError:
        pass

    try:
        return _loads_json_bytes(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        try:
            text = _decode_text(payload)
            documents = [json.loads(line) for line in text.splitlines() if line.strip()]
            if documents:
                return _merge_documents(documents)
        except (UnicodeDecodeError, json.JSONDecodeError):
            pass
        raise AemetError("El producto descargado no contiene JSON reconocible") from error


def _decode_text(payload: bytes) -> str:
    try:
        return payload.decode("utf-8-sig")
    except UnicodeDecodeError:
        # Varios productos históricos de predicción municipal de AEMET se
        # distribuyen todavía como ISO-8859-15.
        return payload.decode("iso-8859-15")


def _loads_json_bytes(payload: bytes) -> Any:
    return json.loads(_decode_text(payload))


def save_download(download: ProductDownload, directory: Path, stem: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{stem}.envelope.json").write_text(
        json.dumps(download.envelope, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    suffix = _payload_suffix(download.payload, download.content_type)
    payload_path = directory / f"{stem}.data{suffix}"
    payload_path.write_bytes(download.payload)
    return payload_path


def save_image_download(
    download: ImageDownload, directory: Path, stem: str
) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    suffix = _image_suffix(download.payload, download.content_type)
    image_path = directory / f"{stem}{suffix}"
    image_path.write_bytes(download.payload)
    return image_path


def _merge_documents(documents: list[Any]) -> Any:
    if len(documents) == 1:
        return documents[0]
    merged: list[Any] = []
    for document in documents:
        if isinstance(document, list):
            merged.extend(document)
        else:
            merged.append(document)
    return merged


def _payload_suffix(payload: bytes, content_type: str) -> str:
    if payload.startswith(b"\x1f\x8b"):
        return ".gz"
    if payload.startswith(b"PK\x03\x04"):
        return ".zip"
    if "xml" in content_type:
        return ".xml"
    if "tar" in content_type:
        return ".tar"
    if "json" in content_type or payload.lstrip().startswith((b"[", b"{")):
        return ".json"
    return ".bin"


def _image_suffix(payload: bytes, content_type: str) -> str:
    if payload.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if payload.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if payload.startswith((b"GIF87a", b"GIF89a")):
        return ".gif"
    if payload.startswith(b"RIFF") and payload[8:12] == b"WEBP":
        return ".webp"
    raise AemetError(
        f"La descarga del mapa no contiene una imagen reconocible ({content_type})"
    )
