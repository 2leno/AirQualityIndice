"""Transform: normalisation, qualite, schema flocon, enrichissement.

Cycle:
  1. Audit qualite des donnees brutes
  2. Normalisation des champs textuels
  3. Construction du schema flocon (6 tables)
  4. Enrichissement: exceeds_who_threshold
  5. Audit final de la table de faits
"""

import logging
from pathlib import Path

import pandas as pd

from aqi_config.settings import settings
from src.quality import quality_report_stage, PHYSICAL_RANGES

logger = logging.getLogger(__name__)

DATA_DIR = Path("data")
CLEAN_DIR = DATA_DIR / "clean"

# Colonnes du fichier clean/ (wide format : une ligne par ville/heure)
CLEAN_COLUMNS = [
    "city_name", "latitude", "longitude", "timestamp",
    "european_aqi", "us_aqi",
    "pm2_5", "pm10",
    "nitrogen_dioxide", "ozone", "sulphur_dioxide", "carbon_monoxide",
]

CLEAN_FILENAME = "air_quality.csv"

POLLUTANT_META = {
    "european_aqi": {"name": "European Air Quality Index", "threshold": None, "unit": "index"},
    "us_aqi": {"name": "US Air Quality Index", "threshold": None, "unit": "index"},
    "pm2_5": {"name": "PM2.5", "threshold": 15, "unit": "ug/m3"},
    "pm10": {"name": "PM10", "threshold": 45, "unit": "ug/m3"},
    "nitrogen_dioxide": {"name": "Nitrogen Dioxide", "threshold": 25, "unit": "ug/m3"},
    "ozone": {"name": "Ozone", "threshold": 100, "unit": "ug/m3"},
    "sulphur_dioxide": {"name": "Sulphur Dioxide", "threshold": 40, "unit": "ug/m3"},
    "carbon_monoxide": {"name": "Carbon Monoxide", "threshold": 10000, "unit": "ug/m3"},
}


def transform_data(raw: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Point d'entree du Transform. Retourne les 6 tables du schema flocon.
    Sauvegarde aussi le fichier clean/ conforme au contrat de donnees.
    """

    # ---- Etape 1 : Audit qualite ----
    quality_report_stage(
        "raw",
        raw,
        ranges=PHYSICAL_RANGES,
        subset_duplicates=["city_name", "timestamp"],
    )

    # ---- Etape 2 : Normalisation ----
    raw["city_name"] = raw["city_name"].str.strip().str.title()

    # ---- Etape 3 : Construction du schema flocon ----
    dim_region = _build_dim_region()
    dim_city = _build_dim_city(dim_region)
    dim_pollutant_category = _build_dim_pollutant_category()
    dim_pollutant = _build_dim_pollutant(dim_pollutant_category)
    dim_date = _build_dim_date(raw["timestamp"].unique())
    fact = _build_fact(raw, dim_city, dim_date, dim_pollutant)

    # ---- Etape 4 : Enrichissement ----
    fact["exceeds_who_threshold"] = _compute_exceeds_threshold(fact, dim_pollutant)

    # ---- Etape 5 : Audit final ----
    quality_report_stage("fact", fact)

    # ---- Etape 6 : Sauvegarde du fichier clean/ ----
    save_clean_data(raw)

    result = {
        "dim_region": dim_region,
        "dim_city": dim_city,
        "dim_pollutant_category": dim_pollutant_category,
        "dim_pollutant": dim_pollutant,
        "dim_date": dim_date,
        "fact_air_quality": fact,
    }
    # Les NaN ne passent pas en JSON (Airflow XCom).
    # astype(object) permet de stocker None dans des colonnes float.
    for key in result:
        result[key] = result[key].astype(object).where(
            pd.notna(result[key]), None
        )
    return result


# ─── Dimensions ─────────────────────────────────────────────────────────────


def _build_dim_region() -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / "dim_region.csv")
    logger.info("[DimRegion] %d regions chargees", len(df))
    return df


def _build_dim_city(dim_region: pd.DataFrame) -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / "dim_city.csv")
    n = len(df)
    logger.info("[DimCity] %d villes chargees", n)
    return df


def _build_dim_pollutant_category() -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / "dim_pollutant_category.csv")
    logger.info("[DimPollCat] %d categories chargees", len(df))
    return df


def _build_dim_pollutant(
    dim_pollutant_category: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    for code, meta in POLLUTANT_META.items():
        # Determiner la category_id
        if code in ("european_aqi", "us_aqi"):
            cat_id = 1
        elif code in ("pm2_5", "pm10"):
            cat_id = 2
        else:
            cat_id = 3

        rows.append({
            "pollutant_id": len(rows) + 1,
            "pollutant_code": code,
            "pollutant_name": meta["name"],
            "unit": meta["unit"],
            "who_threshold": meta["threshold"],
            "category_id": cat_id,
        })
    df = pd.DataFrame(rows)
    logger.info("[DimPollutant] %d polluants avec FK category", len(df))
    return df


def _build_dim_date(timestamps: pd.Index) -> pd.DataFrame:
    df = pd.DataFrame({"full_datetime": pd.to_datetime(timestamps)})
    # date_id deterministe : heures ecoulees depuis 2025-01-01
    # Evite les conflits PK entre runs DAG et backfill
    epoch = pd.Timestamp("2025-01-01")
    df["date_id"] = (
        (df["full_datetime"] - epoch).dt.total_seconds() / 3600
    ).astype("int32")
    df["hour"] = df["full_datetime"].dt.hour
    df["day"] = df["full_datetime"].dt.day
    df["month"] = df["full_datetime"].dt.month
    df["year"] = df["full_datetime"].dt.year
    df["quarter"] = df["full_datetime"].dt.quarter
    df["day_of_week"] = df["full_datetime"].dt.dayofweek
    df["full_datetime"] = df["full_datetime"].dt.strftime("%Y-%m-%dT%H:%M:%S")
    logger.info("[DimDate] %d dates generees", len(df))
    return df


# ─── Faits ──────────────────────────────────────────────────────────────────


def _build_fact(
    raw: pd.DataFrame,
    dim_city: pd.DataFrame,
    dim_date: pd.DataFrame,
    dim_pollutant: pd.DataFrame,
) -> pd.DataFrame:
    id_vars = ["city_name", "timestamp"]
    value_vars = list(POLLUTANT_META.keys())
    fact = raw.melt(
        id_vars=id_vars,
        value_vars=value_vars,
        var_name="pollutant_code",
        value_name="value",
    )

    # FK vers dim_city
    fact = fact.merge(
        dim_city[["city_name", "city_id"]],
        on="city_name",
    )

    # FK vers dim_date
    fact = fact.merge(
        dim_date[["full_datetime", "date_id"]],
        left_on="timestamp",
        right_on="full_datetime",
    )

    # FK vers dim_pollutant
    fact = fact.merge(
        dim_pollutant[["pollutant_code", "pollutant_id"]],
        on="pollutant_code",
    )

    # Colonnes finales: uniquement les mesures + FKs
    result = fact[["city_id", "date_id", "pollutant_id", "value"]].copy()

    logger.info("[Fact] %d lignes dans fact_air_quality", len(result))
    return result


# ─── Enrichissement ─────────────────────────────────────────────────────────


def _compute_exceeds_threshold(
    fact: pd.DataFrame,
    dim_pollutant: pd.DataFrame,
) -> pd.Series:
    """Compare chaque mesure au seuil OMS du polluant correspondant.
    Les indices AQI (threshold=None) sont exclus du calcul.
    Retourne une Serie booleenne alignee sur l'index de `fact`.
    """
    threshold_map = dim_pollutant.set_index("pollutant_id")["who_threshold"]
    # Ignorer les polluants sans seuil (None = indices AQI)
    has_threshold = fact["pollutant_id"].map(threshold_map).notna()
    exceeds = pd.Series(False, index=fact.index, dtype="bool")
    exceeds.loc[has_threshold] = (
        fact.loc[has_threshold, "value"]
        > fact.loc[has_threshold, "pollutant_id"].map(threshold_map)
    ).values
    n_exceed = exceeds.sum()
    logger.info(
        "[Enrich] %d/%d mesures depassent le seuil OMS (indices AQI exclus)",
        n_exceed,
        len(fact),
    )
    return exceeds


# ─── Clean CSV ──────────────────────────────────────────────────────────────


def save_clean_data(raw: pd.DataFrame) -> str:
    """Sauvegarde le fichier clean/ (wide format : une ligne par ville/heure).
    
    Format impose par le contrat de donnees :
    - Tri chronologique
    - Pas de doublons (meme ville + meme heure)
    - Colonnes : city_name, latitude, longitude, timestamp, + polluants
    """
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    filepath = CLEAN_DIR / CLEAN_FILENAME

    df = raw[CLEAN_COLUMNS].copy()
    df = df.sort_values(["timestamp", "city_name"])
    df = df.drop_duplicates(subset=["city_name", "timestamp"])
    df.to_csv(filepath, index=False)

    logger.info("[Clean] Fichier clean sauvegarde : %s (%d lignes)", filepath, len(df))
    return str(filepath)
