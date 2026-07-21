from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    open_meteo_api_url: str = "https://air-quality-api.open-meteo.com/v1/air-quality"
    database_url: str = "postgresql://aqi:aqi@localhost:5432/aqi"
    log_level: str = "INFO"
    airflow_home: str = "./airflow"
    dim_city_csv: str = "data/dim_city.csv"

    email_host: str = "smtp.gmail.com"
    email_port: int = 587
    email_user: str = ""
    email_password: str = ""
    email_recipient: str = ""

    schedule_interval: str = "0 * * * *"
    aqi_alert_threshold: int = 4

    cities: list[dict[str, str | float]] = [
        {"name": "Antananarivo", "lat": -18.8792, "lon": 47.5079},
        {"name": "Toamasina", "lat": -18.149, "lon": 49.4028},
        {"name": "Mahajanga", "lat": -15.7167, "lon": 46.3167},
        {"name": "Fianarantsoa", "lat": -21.4333, "lon": 47.0833},
        {"name": "Antsiranana", "lat": -12.3, "lon": 49.2833},
    ]


settings = Settings()
