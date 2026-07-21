import logging

import pandas as pd
from sqlalchemy import create_engine, exc, text, Table as SATable, MetaData
from sqlalchemy.dialects.postgresql import insert as pg_insert

from aqi_config.settings import settings

logger = logging.getLogger(__name__)

BATCH_SIZE = 5000

CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS dim_region (
    region_id INTEGER PRIMARY KEY,
    region_name VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS dim_city (
    city_id INTEGER PRIMARY KEY,
    city_name VARCHAR(100) NOT NULL UNIQUE,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    region_id INTEGER REFERENCES dim_region(region_id)
);

CREATE TABLE IF NOT EXISTS dim_pollutant_category (
    category_id INTEGER PRIMARY KEY,
    category_name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT
);

CREATE TABLE IF NOT EXISTS dim_pollutant (
    pollutant_id INTEGER PRIMARY KEY,
    pollutant_code VARCHAR(50) NOT NULL UNIQUE,
    pollutant_name VARCHAR(100),
    unit VARCHAR(20),
    who_threshold DOUBLE PRECISION,
    category_id INTEGER REFERENCES dim_pollutant_category(category_id)
);

CREATE TABLE IF NOT EXISTS dim_date (
    date_id INTEGER PRIMARY KEY,
    full_datetime TIMESTAMP NOT NULL UNIQUE,
    hour INTEGER,
    day INTEGER,
    month INTEGER,
    year INTEGER,
    quarter INTEGER,
    day_of_week INTEGER
);

CREATE TABLE IF NOT EXISTS fact_air_quality (
    fact_id SERIAL PRIMARY KEY,
    city_id INTEGER REFERENCES dim_city(city_id),
    date_id INTEGER REFERENCES dim_date(date_id),
    pollutant_id INTEGER REFERENCES dim_pollutant(pollutant_id),
    value DOUBLE PRECISION,
    exceeds_who_threshold BOOLEAN DEFAULT FALSE,
    UNIQUE (city_id, date_id, pollutant_id)
);
"""

LOAD_ORDER = [
    "dim_region",
    "dim_pollutant_category",
    "dim_city",
    "dim_pollutant",
    "dim_date",
    "fact_air_quality",
]


def _ensure_tables(engine) -> None:
    with engine.begin() as connection:
        for statement in CREATE_TABLES_SQL.split(";"):
            statement = statement.strip()
            if statement:
                connection.execute(text(statement))


def _insert_with_conflict_handling(
    data_frame: pd.DataFrame,
    table_name: str,
    engine,
) -> int:
    table_ref = SATable(table_name, MetaData(), autoload_with=engine)
    rows = data_frame.to_dict(orient="records")
    if not rows:
        return 0

    total_inserted = 0
    chunk_count = (len(rows) + BATCH_SIZE - 1) // BATCH_SIZE
    for chunk_idx, chunk_start in enumerate(range(0, len(rows), BATCH_SIZE)):
        chunk = rows[chunk_start : chunk_start + BATCH_SIZE]
        insert_statement = pg_insert(table_ref).values(chunk)
        insert_statement = insert_statement.on_conflict_do_nothing()

        with engine.begin() as connection:
            result = connection.execute(insert_statement)
            total_inserted += result.rowcount

        if chunk_count > 1:
            logger.info(
                "[Load] %s: lot %d/%d termine (%d lignes)",
                table_name,
                chunk_idx + 1,
                chunk_count,
                len(chunk),
            )

    return total_inserted


def load_data(tables: dict[str, pd.DataFrame]) -> None:
    engine = create_engine(settings.database_url)
    _ensure_tables(engine)

    total_inserted = 0
    for table_name in LOAD_ORDER:
        data_frame = tables[table_name]
        if data_frame.empty:
            continue

        try:
            row_count = _insert_with_conflict_handling(data_frame, table_name, engine)
            total_inserted += row_count
            logger.info(
                "[Load] %s: %d lignes inserees",
                table_name,
                row_count,
            )
        except Exception:
            logger.exception("[Load] Erreur lors du chargement de %s", table_name)
            raise

    logger.info(
        "[Load] Chargement termine: %d lignes inserees dans %d tables",
        total_inserted,
        len(LOAD_ORDER),
    )


load_data_backfill = load_data
