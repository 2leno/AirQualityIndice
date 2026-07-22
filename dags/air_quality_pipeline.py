import pendulum

import pandas as pd
from airflow.sdk import dag, task

from aqi_config.logging import setup_logging
from aqi_config.settings import settings
from dags.config import (
    DAG_CATCHUP,
    DAG_ID,
    DAG_SCHEDULE,
    DAG_TAGS,
    DAG_MAX_ACTIVE_RUNS,
    DEFAULT_ARGS,
    DAG_DESCRIPTION,
)
from src.alert import check_and_alert
from src.extract import extract_data, save_raw_data
from src.load import load_data
from src.transform import transform_data

setup_logging()


@dag(
    dag_id=DAG_ID,
    description=DAG_DESCRIPTION,
    schedule=DAG_SCHEDULE,
    start_date=pendulum.datetime(2026, 7, 8, tz="UTC"),
    catchup=DAG_CATCHUP,
    default_args=DEFAULT_ARGS,
    max_active_runs=DAG_MAX_ACTIVE_RUNS,
    tags=DAG_TAGS,
)
def air_quality_pipeline():

    @task
    def extract() -> list[dict]:
        raw = extract_data()
        return raw.to_dict(orient="records")

    @task
    def save_raw(raw_records: list[dict]) -> None:
        raw = pd.DataFrame(raw_records)
        save_raw_data(raw)

    @task
    def transform(raw_records: list[dict]) -> dict:
        raw = pd.DataFrame(raw_records)
        tables = transform_data(raw)
        return {name: df.to_dict(orient="records") for name, df in tables.items()}

    @task
    def load(tables_dict: dict) -> None:
        tables = {name: pd.DataFrame(rec) for name, rec in tables_dict.items()}
        load_data(tables)

    @task
    def alert(tables_dict: dict) -> None:
        tables = {name: pd.DataFrame(rec) for name, rec in tables_dict.items()}
        check_and_alert(
            tables["fact_air_quality"],
            tables["dim_city"],
            tables["dim_pollutant"],
        )

    raw_data = extract()
    save_raw(raw_data)
    transformed = transform(raw_data)
    load(transformed)
    alert(transformed)


dag = air_quality_pipeline()