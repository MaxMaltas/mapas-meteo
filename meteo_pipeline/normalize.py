from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

SPANISH_WEEKDAYS = (
    "lunes",
    "martes",
    "miércoles",
    "jueves",
    "viernes",
    "sábado",
    "domingo",
)


def validate_config(config: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    for item in config.get("temperatures", []):
        if item.get("enabled", True) is False:
            continue
        if not _configured_municipalities(item):
            problems.append(f"Faltan municipios para {item.get('slot', '?')}")
    for item in config.get("forecast_zones", []):
        if item.get("enabled", True) is False:
            continue
        if not _configured_municipalities(item):
            problems.append(f"Faltan municipios para {item.get('slot', '?')}")
    return problems


def build_daily_document(
    daily_data: Any,
    hourly_data: Any,
    config: dict[str, Any],
    target_date: date,
    alerts_path: str,
    alerts_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    daily_index = _index_municipalities(daily_data)
    hourly_index = _index_municipalities(hourly_data)
    warnings: list[str] = []

    temperatures = []
    for slot in config.get("temperatures", []):
        enabled = slot.get("enabled", True) is not False
        configured = _configured_municipalities(slot)
        components = []
        maxima = []
        for location in configured:
            municipality_id = location["id"]
            municipality = daily_index.get(municipality_id) if enabled else None
            maximum = _daily_maximum(municipality, target_date) if municipality else None
            if enabled and maximum is None:
                warnings.append(
                    f"Sin máxima para {slot.get('slot')} · {location['name']} ({municipality_id})"
                )
            elif maximum is not None:
                maxima.append(maximum)
            components.append(
                {"municipality_id": municipality_id, "name": location["name"], "max_c": maximum}
            )
        aggregation = slot.get("aggregation", "maximum")
        if aggregation != "maximum":
            warnings.append(
                f"Agregación de temperatura desconocida para {slot.get('slot')}: "
                f"{aggregation}; se usa maximum"
            )
        maximum = max(maxima) if maxima else None
        temperatures.append(
            {
                "slot": slot.get("slot"),
                "enabled": enabled,
                "label": slot.get("label", ""),
                "municipality_ids": [item["id"] for item in configured],
                "aggregation": "maximum",
                "components": components,
                "max_c": maximum,
                "ae_layer_index": slot.get("ae_layer_index"),
            }
        )

    day_1 = target_date + timedelta(days=1)
    day_2 = target_date + timedelta(days=2)
    forecast_1 = _forecast_for_date(
        day_1, hourly_index, daily_index, config, warnings
    )
    forecast_2 = _forecast_for_date(
        day_2, hourly_index, daily_index, config, warnings
    )

    try:
        timezone = ZoneInfo(config.get("timezone", "Europe/Madrid"))
    except ZoneInfoNotFoundError:
        # Python en Windows puede no incluir la base IANA. La máquina de producción
        # ya opera en hora peninsular, por lo que su zona local es el respaldo correcto.
        timezone = datetime.now().astimezone().tzinfo
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone).isoformat(timespec="seconds"),
        "provider": "AEMET OpenData",
        "scope": config.get("scope", "peninsula_canarias_baleares"),
        "settings": config.get("forecast_selection", {}),
        "alerts": dict(
            alerts_summary
            or {
                "date": target_date.isoformat(),
                "criterion": "pending",
                "provinces": [],
            },
            raw_source=alerts_path,
            map_status="pending_renderer",
        ),
        "clips": {
            "TEMPERATURAS": {
                "date": target_date.isoformat(),
                "values": temperatures,
            },
            "PREVISION": {
                "date": day_1.isoformat(),
                "weekday": SPANISH_WEEKDAYS[day_1.weekday()],
                "zones": forecast_1,
            },
            "DOBLE": {
                "day_1": {
                    "date": day_1.isoformat(),
                    "weekday": SPANISH_WEEKDAYS[day_1.weekday()],
                    "zones": forecast_1,
                },
                "day_2": {
                    "date": day_2.isoformat(),
                    "weekday": SPANISH_WEEKDAYS[day_2.weekday()],
                    "zones": forecast_2,
                },
            },
        },
        "warnings": warnings,
    }


def _forecast_for_date(
    target_date: date,
    hourly_index: dict[str, dict[str, Any]],
    daily_index: dict[str, dict[str, Any]],
    config: dict[str, Any],
    warnings: list[str],
) -> list[dict[str, Any]]:
    output = []
    hour = int(config.get("forecast_selection", {}).get("hour", 12))
    fallback_periods = config.get("forecast_selection", {}).get(
        "fallback_periods", ["12-18", "12-24", "00-24"]
    )
    symbol_map = config.get("symbol_map", {})
    symbol_priority = config.get(
        "symbol_priority",
        {
            "SOL": 10,
            "SOL_NUBE": 20,
            "NUBES_ALTAS": 25,
            "NUBE": 30,
            "VIENTO": 50,
            "SOL_LLUVIA": 55,
            "LLUVIA": 60,
            "NIEVE": 70,
            "TORMENTA": 80,
        },
    )

    for slot in config.get("forecast_zones", []):
        enabled = slot.get("enabled", True) is not False
        configured = _configured_municipalities(slot)
        components = []
        for location in configured:
            municipality_id = location["id"]
            sky = (
                _hourly_sky(hourly_index.get(municipality_id), target_date, hour)
                if enabled
                else None
            )
            source = "hourly"
            if enabled and sky is None:
                sky = _daily_sky(
                    daily_index.get(municipality_id), target_date, fallback_periods
                )
                source = "daily_fallback"
            code = _sky_code(_sky_value(sky)) if sky else ""
            symbol = symbol_map.get(code)
            if enabled and not symbol:
                warnings.append(
                    f"Sin símbolo para {slot.get('slot')} · {location['name']} "
                    f"({municipality_id}), código {code or 'vacío'}"
                )
            components.append(
                {
                    "municipality_id": municipality_id,
                    "name": location["name"],
                    "aemet_code": code,
                    "description": (sky or {}).get("descripcion", ""),
                    "symbol": symbol,
                    "source": source if sky else None,
                }
            )
        selected = max(
            (item for item in components if item["symbol"]),
            key=lambda item: symbol_priority.get(item["symbol"], 0),
            default=None,
        )
        selected_symbol = selected["symbol"] if selected else None
        component_symbols = {item["symbol"] for item in components if item["symbol"]}
        sunny_symbols = {"SOL", "SOL_NUBE", "NUBES_ALTAS"}
        if selected_symbol == "LLUVIA" and component_symbols & sunny_symbols:
            selected_symbol = "SOL_LLUVIA"
        output.append(
            {
                "slot": slot.get("slot"),
                "enabled": enabled,
                "label": slot.get("label", ""),
                "municipality_ids": [item["id"] for item in configured],
                "aggregation": slot.get("aggregation", "most_significant"),
                "components": components,
                "aemet_code": selected["aemet_code"] if selected else "",
                "description": selected["description"] if selected else "",
                "symbol": selected_symbol,
                "source": selected["source"] if selected else None,
                "prevision_layer_index": slot.get("prevision_layer_index"),
                "doble_day_1_layer_index": slot.get("doble_day_1_layer_index"),
                "doble_day_2_layer_index": slot.get("doble_day_2_layer_index"),
            }
        )
    return output


def _index_municipalities(data: Any) -> dict[str, dict[str, Any]]:
    documents = data if isinstance(data, list) else [data]
    index: dict[str, dict[str, Any]] = {}
    for document in documents:
        if not isinstance(document, dict):
            continue
        if isinstance(document.get("root"), dict):
            document = document["root"]
        if "prediccion" in document:
            identifier = _normalise_id(document.get("id") or document.get("municipio"))
            if identifier:
                index[identifier] = document
        else:
            for value in document.values():
                if isinstance(value, list):
                    index.update(_index_municipalities(value))
    return index


def _normalise_id(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return text.zfill(5) if text.isdigit() else text


def _configured_municipalities(item: dict[str, Any]) -> list[dict[str, str]]:
    raw = item.get("municipalities")
    if raw is None:
        raw = [item.get("municipality_id")] if item.get("municipality_id") else []
    output = []
    for location in raw:
        if isinstance(location, dict):
            identifier = _normalise_id(location.get("id"))
            name = str(location.get("name", "")).strip()
        else:
            identifier = _normalise_id(location)
            name = ""
        if identifier:
            output.append({"id": identifier, "name": name or identifier})
    return output


def _days(municipality: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not municipality:
        return []
    prediction = municipality.get("prediccion", {})
    days = prediction.get("dia", []) if isinstance(prediction, dict) else []
    return days if isinstance(days, list) else []


def _day_for_date(
    municipality: dict[str, Any] | None, target_date: date
) -> dict[str, Any] | None:
    for day in _days(municipality):
        raw_date = str(day.get("fecha", ""))[:10]
        if raw_date == target_date.isoformat():
            return day
    return None


def _daily_maximum(municipality: dict[str, Any] | None, target_date: date) -> int | float | None:
    day = _day_for_date(municipality, target_date)
    temperature = day.get("temperatura", {}) if day else {}
    value = temperature.get("maxima") if isinstance(temperature, dict) else None
    if value is None or value == "":
        return None
    try:
        number = float(value)
        return int(number) if number.is_integer() else number
    except (TypeError, ValueError):
        return None


def _hourly_sky(
    municipality: dict[str, Any] | None, target_date: date, hour: int
) -> dict[str, Any] | None:
    day = _day_for_date(municipality, target_date)
    entries = _sky_entries(day)
    for entry in entries:
        period = str(entry.get("periodo", "")).zfill(2)
        if period == str(hour).zfill(2) and _sky_value(entry):
            return entry
    return None


def _daily_sky(
    municipality: dict[str, Any] | None,
    target_date: date,
    preferred_periods: list[str],
) -> dict[str, Any] | None:
    day = _day_for_date(municipality, target_date)
    entries = _sky_entries(day)
    for period in preferred_periods:
        for entry in entries:
            if str(entry.get("periodo", "")) == period and _sky_value(entry):
                return entry
    return next((entry for entry in entries if _sky_value(entry)), None)


def _sky_code(value: Any) -> str:
    match = re.match(r"^(\d+)", str(value or ""))
    return match.group(1) if match else ""


def _sky_entries(day: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not day:
        return []
    entries = day.get("estadoCielo", day.get("estado_cielo", []))
    return entries if isinstance(entries, list) else []


def _sky_value(entry: dict[str, Any]) -> Any:
    return entry.get("value", entry.get("valor"))
