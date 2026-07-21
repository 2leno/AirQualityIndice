import logging
from pathlib import Path

import pandas as pd
import openmeteo_requests

from aqi_config.settings import settings
from src.quality import quality_report_stage, PHYSICAL_RANGES

logger = logging.getLogger(__name__)

CURRENT_PARAMETERS = [
    "european_aqi",
    "us_aqi",
    "pm2_5",
    "pm10",
    "nitrogen_dioxide",
    "ozone",
    "sulphur_dioxide",
    "carbon_monoxide",
]

RAW_DIR = Path("data/raw")
BACKFILL_DIR = RAW_DIR / "backfill"


def extract_data() -> pd.DataFrame:
    """Appelle l'API Open-Meteo Air Quality pour chaque ville.
    Loggue un rapport de qualite sur les donnees recues.
    """
    om = openmeteo_requests.Client()
    records = []

    for city in settings.cities:
        params = {
            "latitude": city["lat"],
            "longitude": city["lon"],
            "current": CURRENT_PARAMETERS,
        }

        try:
            responses = om.weather_api(settings.open_meteo_api_url, params=params)
            current = responses[0].Current()
        except Exception:
            logger.exception(
                "[Extract] API error for %s (%s, %s)",
                city["name"],
                city["lat"],
                city["lon"],
            )
            # On continue avec les autres villes (reponse question #2)
            continue

        record = {
            "city_name": city["name"],
            "latitude": city["lat"],
            "longitude": city["lon"],
            "timestamp": pd.Timestamp(current.Time(), unit="s").isoformat(),
        }

        for i in range(min(len(CURRENT_PARAMETERS), current.VariablesLength())):
            record[CURRENT_PARAMETERS[i]] = current.Variables(i).Value()

        records.append(record)

    df = pd.DataFrame(records)

    # Rapport qualite sur les donnees extraites
    quality_report_stage(
        "extract",
        df,
        ranges=PHYSICAL_RANGES,
        subset_duplicates=["city_name", "timestamp"],
    )

    return df


def save_raw_data(df: pd.DataFrame) -> str:
    """Sauvegarde les donnees brutes dans data/raw/ avec timestamp.
    Cree un fichier par ville (conforme au contrat : "un fichier par ville et par appel").
    Sert de point de recuperation (data lake local).

    Retourne le repertoire contenant les fichiers.
    """
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    ts = df["timestamp"].iloc[0].replace(":", "-").replace("T", "_")

    for _, row in df.iterrows():
        city = row["city_name"].lower().replace(" ", "_")
        filename = f"air_quality_{city}_{ts}.csv"
        filepath = RAW_DIR / filename
        pd.DataFrame([row]).to_csv(filepath, index=False)

    logger.info("[SaveRaw] %d fichiers sauvegardes dans %s", len(df), RAW_DIR)

    return str(RAW_DIR)


def extract_data_range(
    city: dict,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    om = openmeteo_requests.Client()
    params = {
        "latitude": city["lat"],
        "longitude": city["lon"],
        "hourly": CURRENT_PARAMETERS,
        "start_date": start_date,
        "end_date": end_date,
        "timezone": "UTC",
    }

    try:
        responses = om.weather_api(settings.open_meteo_api_url, params=params)
        hourly = responses[0].Hourly()
    except Exception:
        logger.exception(
            "[ExtractRange] API error for %s (%s, %s) range %s -> %s",
            city["name"],
            city["lat"],
            city["lon"],
            start_date,
            end_date,
        )
        return pd.DataFrame()

    start_timestamp = hourly.Time()
    interval_seconds = hourly.Interval()
    variable_count = hourly.VariablesLength()

    if variable_count == 0:
        return pd.DataFrame()

    row_count = len(hourly.Variables(0).ValuesAsNumpy())
    records = []
    for row_index in range(row_count):
        record = {
            "city_name": city["name"],
            "latitude": city["lat"],
            "longitude": city["lon"],
            "timestamp": pd.Timestamp(
                start_timestamp + row_index * interval_seconds, unit="s"
            ).isoformat(),
        }
        for variable_index in range(min(len(CURRENT_PARAMETERS), variable_count)):
            record[CURRENT_PARAMETERS[variable_index]] = (
                hourly.Variables(variable_index).ValuesAsNumpy()[row_index]
            )
        records.append(record)

    df = pd.DataFrame(records)
    logger.info(
        "[ExtractRange] %s: %d lignes du %s au %s",
        city["name"],
        len(df),
        start_date,
        end_date,
    )
    return df
