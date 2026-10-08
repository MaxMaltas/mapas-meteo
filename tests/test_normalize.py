import json
import unittest
from datetime import date
from pathlib import Path

from meteo_pipeline.normalize import build_daily_document


ROOT = Path(__file__).resolve().parents[1]


class NormalizeTests(unittest.TestCase):
    def test_maximum_and_hourly_with_daily_fallback(self) -> None:
        daily = json.loads((ROOT / "tests/fixtures/daily.json").read_text(encoding="utf-8"))
        hourly = json.loads((ROOT / "tests/fixtures/hourly.json").read_text(encoding="utf-8"))
        config = {
            "timezone": "Europe/Madrid",
            "scope": "peninsula_canarias_baleares",
            "forecast_selection": {"hour": 12, "fallback_periods": ["12-18"]},
            "temperatures": [
                {"slot": "TEMP_01", "municipality_id": "28079", "label": "Madrid", "ae_layer_index": 1}
            ],
            "forecast_zones": [
                {
                    "slot": "ZONA_01",
                    "municipality_id": "28079",
                    "label": "Centro",
                    "prevision_layer_index": 1,
                    "doble_day_1_layer_index": 15,
                    "doble_day_2_layer_index": 1
                }
            ],
            "symbol_map": {"12": "SOL_NUBE", "45": "LLUVIA"}
        }
        document = build_daily_document(
            daily, hourly, config, date(2026, 9, 25), "avisos.xml"
        )

        self.assertEqual(document["clips"]["TEMPERATURAS"]["values"][0]["max_c"], 31)
        self.assertEqual(document["clips"]["PREVISION"]["zones"][0]["symbol"], "SOL_NUBE")
        self.assertEqual(document["clips"]["PREVISION"]["zones"][0]["source"], "hourly")
        self.assertEqual(document["clips"]["DOBLE"]["day_2"]["zones"][0]["symbol"], "LLUVIA")
        self.assertEqual(document["clips"]["DOBLE"]["day_2"]["zones"][0]["source"], "daily_fallback")

    def test_uses_highest_temperature_and_most_significant_symbol(self) -> None:
        daily = json.loads((ROOT / "tests/fixtures/daily.json").read_text(encoding="utf-8"))
        hourly = json.loads((ROOT / "tests/fixtures/hourly.json").read_text(encoding="utf-8"))
        second_daily = json.loads(json.dumps(daily[0]))
        second_daily["id"] = "41091"
        second_daily["nombre"] = "Sevilla"
        second_daily["prediccion"]["dia"][0]["temperatura"]["maxima"] = 34
        daily.append(second_daily)
        second_hourly = json.loads(json.dumps(hourly[0]))
        second_hourly["id"] = "41091"
        second_hourly["nombre"] = "Sevilla"
        second_hourly["prediccion"]["dia"][0]["estadoCielo"][0] = {
            "value": "54", "periodo": "12", "descripcion": "Tormenta"
        }
        hourly.append(second_hourly)
        locations = [
            {"id": "28079", "name": "Madrid"},
            {"id": "41091", "name": "Sevilla"},
        ]
        config = {
            "timezone": "Europe/Madrid",
            "forecast_selection": {"hour": 12, "fallback_periods": ["12-18"]},
            "temperatures": [
                {
                    "slot": "TEMP_01",
                    "aggregation": "maximum",
                    "municipalities": locations,
                    "ae_layer_index": 1,
                }
            ],
            "forecast_zones": [
                {
                    "slot": "ZONA_01",
                    "municipalities": locations,
                    "prevision_layer_index": 1,
                    "doble_day_1_layer_index": 15,
                    "doble_day_2_layer_index": 1,
                }
            ],
            "symbol_map": {"12": "SOL_NUBE", "54": "TORMENTA", "45": "LLUVIA"},
            "symbol_priority": {"SOL_NUBE": 20, "LLUVIA": 60, "TORMENTA": 80},
        }
        document = build_daily_document(
            daily, hourly, config, date(2026, 9, 25), "avisos.xml"
        )

        temperature = document["clips"]["TEMPERATURAS"]["values"][0]
        self.assertEqual(temperature["max_c"], 34)
        self.assertEqual(temperature["aggregation"], "maximum")
        self.assertEqual(len(temperature["components"]), 2)
        forecast = document["clips"]["PREVISION"]["zones"][0]
        self.assertEqual(forecast["symbol"], "TORMENTA")
        self.assertEqual(len(forecast["components"]), 2)

    def test_uses_sun_rain_symbol_for_mixed_zone(self) -> None:
        daily = json.loads((ROOT / "tests/fixtures/daily.json").read_text(encoding="utf-8"))
        hourly = json.loads((ROOT / "tests/fixtures/hourly.json").read_text(encoding="utf-8"))
        second_hourly = json.loads(json.dumps(hourly[0]))
        second_hourly["id"] = "41091"
        second_hourly["nombre"] = "Sevilla"
        second_hourly["prediccion"]["dia"][0]["estadoCielo"][0] = {
            "value": "45", "periodo": "12", "descripcion": "Muy nuboso con lluvia escasa"
        }
        hourly.append(second_hourly)
        config = {
            "forecast_selection": {"hour": 12, "fallback_periods": ["12-18"]},
            "temperatures": [],
            "forecast_zones": [{
                "slot": "ZONA_01",
                "municipalities": [
                    {"id": "28079", "name": "Madrid"},
                    {"id": "41091", "name": "Sevilla"},
                ],
                "prevision_layer_index": 1,
                "doble_day_1_layer_index": 15,
                "doble_day_2_layer_index": 1,
            }],
            "symbol_map": {"12": "SOL_NUBE", "45": "LLUVIA"},
        }

        document = build_daily_document(
            daily, hourly, config, date(2026, 9, 25), "avisos.xml"
        )

        forecast = document["clips"]["PREVISION"]["zones"][0]
        self.assertEqual(forecast["symbol"], "SOL_LLUVIA")
        self.assertEqual(
            {component["symbol"] for component in forecast["components"]},
            {"SOL_NUBE", "LLUVIA"},
        )

    def test_project_config_maps_showery_intervals_to_sun_rain(self) -> None:
        config = json.loads((ROOT / "config/meteo.json").read_text(encoding="utf-8"))

        self.assertEqual(config["symbol_files"]["SOL_LLUVIA"], "SOL LLUVIA.mov")
        self.assertEqual(config["symbol_map"]["23"], "SOL_LLUVIA")
        self.assertEqual(config["symbol_map"]["43"], "SOL_LLUVIA")
        self.assertEqual(config["symbol_map"]["24"], "LLUVIA")
        self.assertEqual(config["symbol_map"]["44"], "LLUVIA")

    def test_accepts_bulk_endpoint_root_and_snake_case_fields(self) -> None:
        daily = [{
            "root": {
                "id": "28079",
                "prediccion": {"dia": [{
                    "fecha": "2026-09-25",
                    "temperatura": {"maxima": "31"},
                    "estado_cielo": [{"periodo": "12-18", "valor": "45", "descripcion": "Lluvia"}],
                }]},
            }
        }]
        hourly = [{
            "root": {
                "id": "28079",
                "prediccion": {"dia": [{
                    "fecha": "2026-09-26",
                    "estado_cielo": [{"periodo": "12", "valor": "12", "descripcion": "Poco nuboso"}],
                }]},
            }
        }]
        config = {
            "timezone": "Europe/Madrid",
            "forecast_selection": {"hour": 12, "fallback_periods": ["12-18"]},
            "temperatures": [{
                "slot": "TEMP_01",
                "municipalities": [{"id": "28079", "name": "Madrid"}],
                "ae_layer_index": 1,
            }],
            "forecast_zones": [{
                "slot": "ZONA_01",
                "municipalities": [{"id": "28079", "name": "Madrid"}],
                "prevision_layer_index": 1,
                "doble_day_1_layer_index": 15,
                "doble_day_2_layer_index": 1,
            }],
            "symbol_map": {"12": "SOL_NUBE", "45": "LLUVIA"},
        }
        document = build_daily_document(
            daily, hourly, config, date(2026, 9, 25), "avisos.xml"
        )
        self.assertEqual(document["clips"]["TEMPERATURAS"]["values"][0]["max_c"], 31)
        self.assertEqual(document["clips"]["PREVISION"]["zones"][0]["symbol"], "SOL_NUBE")


if __name__ == "__main__":
    unittest.main()
