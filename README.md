# AQI - Air Quality Index ETL Pipeline

ETL pipeline for air quality monitoring in 5 Madagascar cities (Antananarivo, Toamasina, Mahajanga, Fianarantsoa, Antsiranana). Data is sourced from the Open-Meteo Air Quality API, transformed into a snowflake schema, loaded into PostgreSQL, and orchestrated by Apache Airflow.

## Pipeline

```
Open-Meteo API
      |
[extract.py]  -->  raw CSV (data/raw/)
      |
[transform.py] --> quality checks + snowflake build + clean CSV (data/clean/)
      |
[load.py]     --> PostgreSQL (6 tables, batch INSERT ON CONFLICT DO NOTHING)
      |
[alert.py]    --> email if AQI >= 4 (6h cooldown)
```

### Snowflake Schema (6 tables)

- **dim_region** -- region_id, region_name
- **dim_city** -- city_id, city_name, latitude, longitude, region_id FK
- **dim_pollutant_category** -- category_id, category_name, description
- **dim_pollutant** -- pollutant_id, code, name, unit, WHO threshold, category_id FK
- **dim_date** -- date_id, full_datetime, hour, day, month, year, quarter, day_of_week
- **fact_air_quality** -- city_id FK, date_id FK, pollutant_id FK, value, exceeds_who_threshold

## Tech Stack

| Component | Technology |
|---|---|
| Language | Python 3.11+ |
| Orchestrator | Apache Airflow 3.3 |
| Database | PostgreSQL 16 |
| API | Open-Meteo Air Quality |
| Client | openmeteo-requests |
| Data | Pandas |
| Config | Pydantic-Settings / dotenv |
| SMTP | Email alerts with cooldown |

## Project Structure

```
├── aqi_config/          # Settings (Pydantic) + logging
│   ├── settings.py      # 15 config fields, 6 cities
│   └── logging.py
├── src/                 # Core ETL
│   ├── extract.py       # API extraction (current + historical range)
│   ├── transform.py     # Snowflake transformation + enrichment
│   ├── load.py          # PostgreSQL batch loading
│   ├── quality.py       # Data quality audits (3 stages)
│   └── alert.py         # Email alerts with DB cooldown
├── dags/                # Airflow DAG
│   ├── config.py        # DAG defaults
│   └── air_quality_pipeline.py  # extract → save_raw → transform → load → alert
├── scripts/
│   └── backfill.py      # Historical data download (CLI, up to 12 months)
├── data/                # Reference CSVs (dim_city, dim_region, dim_pollutant_category)
├── docker-compose.yml   # Airflow 3.3 + PostgreSQL 16
├── Dockerfile
├── pyproject.toml
└── .env.example
```

## Deployment

Oracle Cloud Always Free Tier (2 AMD + 4 ARM VM) with Docker Compose.

## Quick Start

```bash
uv sync
cp .env.example .env
# Edit .env with your DB & email credentials
docker compose up -d
```

## Backfill Historical Data

```bash
uv run python scripts/backfill.py                     # last 12 months
uv run python scripts/backfill.py --raw-only           # download only
uv run python scripts/backfill.py --start-date 2026-01 --end-date 2026-06
```

## License

MIT
