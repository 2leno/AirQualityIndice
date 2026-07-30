import os

os.environ["AIRFLOW_HOME"] = os.path.join(os.path.dirname(__file__), "..", "airflow")

import pandas as pd
import pytest

CITIES = ["Antananarivo", "Toamasina", "Mahajanga", "Fianarantsoa", "Antsiranana"]

POLLUTANTS = [
    "european_aqi", "us_aqi", "pm2_5", "pm10",
    "nitrogen_dioxide", "ozone", "sulphur_dioxide", "carbon_monoxide",
]


@pytest.fixture
def sample_raw():
    rows = []
    for city in CITIES:
        rows.append({
            "city_name": city,
            "latitude": -18.0,
            "longitude": 47.0,
            "timestamp": "2026-07-30T12:00:00",
            "european_aqi": 2.0,
            "us_aqi": 3.0,
            "pm2_5": 10.0,
            "pm10": 20.0,
            "nitrogen_dioxide": 5.0,
            "ozone": 30.0,
            "sulphur_dioxide": 2.0,
            "carbon_monoxide": 200.0,
        })
    return pd.DataFrame(rows)


@pytest.fixture
def sample_raw_with_nulls(sample_raw):
    df = sample_raw.copy()
    df.loc[0, "pm2_5"] = None
    df.loc[1, "ozone"] = None
    return df


@pytest.fixture
def sample_dim_city():
    return pd.read_csv("data/dim_city.csv")


@pytest.fixture
def sample_dim_region():
    return pd.read_csv("data/dim_region.csv")


@pytest.fixture
def sample_dim_pollutant_category():
    return pd.read_csv("data/dim_pollutant_category.csv")


@pytest.fixture
def sample_fact():
    rows = []
    for city_id in range(1, 6):
        for date_id in [1, 2]:
            for pollutant_id in range(1, 9):
                rows.append({
                    "city_id": city_id,
                    "date_id": date_id,
                    "pollutant_id": pollutant_id,
                    "value": 15.0,
                    "exceeds_who_threshold": False,
                })
    return pd.DataFrame(rows)
