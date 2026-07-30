import pytest
import pandas as pd
from src.alert import _build_alert_body


class TestBuildAlertBody:
    def test_single_city(self):
        data = pd.DataFrame([
            {"city_name": "Antananarivo", "pollutant_code": "european_aqi", "value": 5.0},
        ])
        body = _build_alert_body(data, 4)
        assert "AQI >= 4" in body
        assert "Antananarivo" in body
        assert "european_aqi" in body

    def test_multiple_cities(self):
        data = pd.DataFrame([
            {"city_name": "Antananarivo", "pollutant_code": "european_aqi", "value": 5.0},
            {"city_name": "Toamasina", "pollutant_code": "us_aqi", "value": 6.0},
        ])
        body = _build_alert_body(data, 4)
        assert "Antananarivo" in body
        assert "Toamasina" in body

    def test_empty_data(self):
        data = pd.DataFrame()
        body = _build_alert_body(data, 4)
        assert "AQI >= 4" in body
