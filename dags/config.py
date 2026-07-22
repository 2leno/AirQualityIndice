from datetime import timedelta

from aqi_config.settings import settings

DEFAULT_ARGS = {
    "owner": "aqi",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

DAG_ID = "air_quality_pipeline"
DAG_TAGS = ["air-quality", "madagascar"]
DAG_SCHEDULE = settings.schedule_interval
DAG_CATCHUP = False
DAG_MAX_ACTIVE_RUNS = 1
DAG_DESCRIPTION = (
    "Extract air quality data from Open-Meteo API, "
    "transform to snowflake schema, load into PostgreSQL, "
    "and send alerts if AQI >= 4"
)