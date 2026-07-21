import argparse
import logging
from calendar import monthrange
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from aqi_config.settings import settings
from src.extract import BACKFILL_DIR, extract_data_range
from src.load import load_data_backfill
from src.transform import transform_data

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("backfill")

BACKFILL_PERIOD_DAYS = 365


def compute_months(start_date: str, end_date: str) -> list[str]:
    months = []
    current_date = datetime.strptime(start_date, "%Y-%m-%d")
    end_date_parsed = datetime.strptime(end_date, "%Y-%m-%d")
    while current_date <= end_date_parsed:
        months.append(current_date.strftime("%Y-%m"))
        if current_date.month == 12:
            current_date = current_date.replace(year=current_date.year + 1, month=1)
        else:
            current_date = current_date.replace(month=current_date.month + 1)
    return months


def month_boundaries(year_month: str) -> tuple[str, str]:
    year, month_number = map(int, year_month.split("-"))
    first_day = datetime(year, month_number, 1)
    last_day_number = monthrange(year, month_number)[1]
    last_day = datetime(year, month_number, last_day_number)
    return first_day.strftime("%Y-%m-%d"), last_day.strftime("%Y-%m-%d")


def is_month_downloaded(city_slug: str, year_month: str) -> bool:
    file_path = BACKFILL_DIR / city_slug / f"{year_month}.csv"
    return file_path.exists()


def download_and_save_month(
    city: dict,
    year_month: str,
    skip_existing: bool,
) -> pd.DataFrame | None:
    city_slug = city["name"].lower().replace(" ", "_")

    if skip_existing and is_month_downloaded(city_slug, year_month):
        logger.info("[Skip] %s %s deja telecharge", city["name"], year_month)
        return None

    start_date, end_date = month_boundaries(year_month)
    api_result = extract_data_range(city, start_date, end_date)

    if api_result.empty:
        return None

    output_directory = BACKFILL_DIR / city_slug
    output_directory.mkdir(parents=True, exist_ok=True)
    output_path = output_directory / f"{year_month}.csv"
    api_result.to_csv(output_path, index=False)
    logger.info(
        "[Save] %s %s -> %s (%d lignes)",
        city["name"],
        year_month,
        output_path,
        len(api_result),
    )
    return api_result


def bulk_load_raw_to_database():
    all_csv_files = sorted(BACKFILL_DIR.rglob("*.csv"))
    if not all_csv_files:
        logger.warning("[Load] Aucun fichier trouve dans %s", BACKFILL_DIR)
        return

    combined_data = pd.concat(
        [pd.read_csv(csv_path) for csv_path in all_csv_files],
        ignore_index=True,
    )
    combined_data = combined_data.sort_values(["timestamp", "city_name"])
    combined_data = combined_data.drop_duplicates(
        subset=["city_name", "timestamp"]
    )

    logger.info(
        "[Load] %d fichiers, %d lignes combinees",
        len(all_csv_files),
        len(combined_data),
    )

    transformed_tables = transform_data(combined_data)
    load_data_backfill(transformed_tables)
    logger.info("[Load] Chargement termine dans PostgreSQL")


def process_backfill(
    cities: list[dict],
    months: list[str],
    raw_only: bool,
    skip_existing: bool,
):
    has_new_data = False
    for city in cities:
        for year_month in months:
            new_data = download_and_save_month(city, year_month, skip_existing)
            if new_data is not None and not new_data.empty:
                has_new_data = True

    if not raw_only and has_new_data:
        logger.info(
            "[Backfill] Nouveaux fichiers trouves, chargement en base..."
        )
        bulk_load_raw_to_database()
    elif not raw_only:
        logger.info(
            "[Backfill] Aucun nouveau fichier, chargement depuis les existants..."
        )
        bulk_load_raw_to_database()


def main():
    parser = argparse.ArgumentParser(
        description="Backfill 12 mois glissants Open-Meteo"
    )
    parser.add_argument(
        "--raw-only",
        action="store_true",
        help="Ne pas charger en base, juste telecharger les CSV",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Ne pas re-telecharger les mois deja dans raw/backfill/",
    )
    parser.add_argument(
        "--from-raw",
        action="store_true",
        help="Recharger les CSV en base sans appel API",
    )
    parser.add_argument(
        "--start-date",
        default=None,
        help="AAAA-MM-JJ. Defaut: 12 mois avant aujourd'hui",
    )
    parser.add_argument(
        "--end-date",
        default=None,
        help="AAAA-MM-JJ. Defaut: aujourd'hui",
    )
    args = parser.parse_args()

    today = datetime.now()
    end_date = args.end_date or today.strftime("%Y-%m-%d")
    start_date = args.start_date or (
        today - timedelta(days=BACKFILL_PERIOD_DAYS)
    ).strftime("%Y-%m-%d")

    if args.from_raw:
        bulk_load_raw_to_database()
        return

    all_months = compute_months(start_date, end_date)
    logger.info(
        "[Backfill] Periode %s -> %s (%d mois, %d villes, raw_only=%s)",
        start_date,
        end_date,
        len(all_months),
        len(settings.cities),
        args.raw_only,
    )

    process_backfill(
        settings.cities, all_months, args.raw_only, args.skip_existing
    )


if __name__ == "__main__":
    main()
