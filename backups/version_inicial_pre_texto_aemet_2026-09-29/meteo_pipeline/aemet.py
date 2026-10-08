from __future__ import annotations

import gzip
import io
import json
import tarfile
import time
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


BASE_URL = "https://opendata.aemet.es/opendata"


class AemetError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProductDownload:
    endpoint: str
    envelope: dict[str, Any]
    payload: bytes
    content_type: str


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
                delay = float(retry_after) if retry_after else min(2 ** attempt, 30)
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
