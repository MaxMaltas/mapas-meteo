from __future__ import annotations

import io
import re
import tarfile
import xml.etree.ElementTree as ET
from datetime import date, datetime, time, timedelta
from typing import Any


CAP_NAMESPACE = {"cap": "urn:oasis:names:tc:emergency:cap:1.2"}
LEVEL_RANK = {"green": 0, "yellow": 1, "orange": 2, "red": 3}
SEVERITY_LEVEL = {
    "Minor": "green",
    "Moderate": "yellow",
    "Severe": "orange",
    "Extreme": "red",
}

# Códigos INE provinciales para Península, Canarias y Baleares.
PROVINCES = {
    "01": "Álava",
    "02": "Albacete",
    "03": "Alicante",
    "04": "Almería",
    "05": "Ávila",
    "06": "Badajoz",
    "07": "Illes Balears",
    "08": "Barcelona",
    "09": "Burgos",
    "10": "Cáceres",
    "11": "Cádiz",
    "12": "Castellón",
    "13": "Ciudad Real",
    "14": "Córdoba",
    "15": "A Coruña",
    "16": "Cuenca",
    "17": "Girona",
    "18": "Granada",
    "19": "Guadalajara",
    "20": "Gipuzkoa",
    "21": "Huelva",
    "22": "Huesca",
    "23": "Jaén",
    "24": "León",
    "25": "Lleida",
    "26": "La Rioja",
    "27": "Lugo",
    "28": "Madrid",
    "29": "Málaga",
    "30": "Murcia",
    "31": "Navarra",
    "32": "Ourense",
    "33": "Asturias",
    "34": "Palencia",
    "35": "Las Palmas",
    "36": "Pontevedra",
    "37": "Salamanca",
    "38": "Santa Cruz de Tenerife",
    "39": "Cantabria",
    "40": "Segovia",
    "41": "Sevilla",
    "42": "Soria",
    "43": "Tarragona",
    "44": "Teruel",
    "45": "Toledo",
    "46": "Valencia",
    "47": "Valladolid",
    "48": "Bizkaia",
    "49": "Zamora",
    "50": "Zaragoza",
}


def summarise_cap_by_province(payload: bytes, target_date: date) -> dict[str, Any]:
    provinces = {
        code: {"code": code, "name": name, "level": "green", "alerts": []}
        for code, name in PROVINCES.items()
    }
    parsed_files = 0

    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:*") as archive:
        for member in archive.getmembers():
            if not member.isfile() or not member.name.lower().endswith(".xml"):
                continue
            extracted = archive.extractfile(member)
            if not extracted:
                continue
            parsed_files += 1
            root = ET.fromstring(extracted.read())
            for info in root.findall("cap:info", CAP_NAMESPACE):
                if not _overlaps_date(info, target_date):
                    continue
                level = _level_for_info(info)
                if level == "green":
                    continue
                event = info.findtext("cap:event", default="", namespaces=CAP_NAMESPACE)
                onset = info.findtext("cap:onset", default="", namespaces=CAP_NAMESPACE)
                expires = info.findtext("cap:expires", default="", namespaces=CAP_NAMESPACE)
                for area in info.findall("cap:area", CAP_NAMESPACE):
                    area_name = area.findtext(
                        "cap:areaDesc", default="", namespaces=CAP_NAMESPACE
                    )
                    for province_code in _province_codes(area):
                        province = provinces.get(province_code)
                        if not province:
                            continue
                        province["alerts"].append(
                            {
                                "level": level,
                                "event": event,
                                "area": area_name,
                                "onset": onset,
                                "expires": expires,
                            }
                        )
                        if LEVEL_RANK[level] > LEVEL_RANK[province["level"]]:
                            province["level"] = level

    return {
        "date": target_date.isoformat(),
        "criterion": "maximum_active_level_in_any_aemet_zone_per_province",
        "parsed_cap_files": parsed_files,
        "provinces": [provinces[code] for code in sorted(provinces)],
    }


def _province_codes(area: ET.Element) -> set[str]:
    result: set[str] = set()
    for geocode in area.findall("cap:geocode", CAP_NAMESPACE):
        value_name = geocode.findtext(
            "cap:valueName", default="", namespaces=CAP_NAMESPACE
        )
        value = geocode.findtext("cap:value", default="", namespaces=CAP_NAMESPACE)
        if "Meteoalerta zona" not in value_name:
            continue
        digits = re.sub(r"\D", "", value)
        if len(digits) >= 4:
            result.add(digits[2:4])
    return result


def _level_for_info(info: ET.Element) -> str:
    event = info.findtext("cap:event", default="", namespaces=CAP_NAMESPACE).lower()
    for word in ("rojo", "naranja", "amarillo"):
        if f"nivel {word}" in event:
            return {"rojo": "red", "naranja": "orange", "amarillo": "yellow"}[word]
    severity = info.findtext("cap:severity", default="", namespaces=CAP_NAMESPACE)
    return SEVERITY_LEVEL.get(severity, "green")


def _overlaps_date(info: ET.Element, target_date: date) -> bool:
    onset_text = info.findtext("cap:onset", default="", namespaces=CAP_NAMESPACE)
    expires_text = info.findtext("cap:expires", default="", namespaces=CAP_NAMESPACE)
    if not onset_text or not expires_text:
        return True
    try:
        onset = datetime.fromisoformat(onset_text.replace("Z", "+00:00"))
        expires = datetime.fromisoformat(expires_text.replace("Z", "+00:00"))
    except ValueError:
        return True
    start = datetime.combine(target_date, time.min, tzinfo=onset.tzinfo)
    end = start + timedelta(days=1)
    return onset < end and expires >= start
