import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import pandas as pd
from sqlalchemy import create_engine, text

from aqi_config.settings import settings

logger = logging.getLogger(__name__)

AQI_POLLUTANTS = ["european_aqi", "us_aqi"]
ALERT_COOLDOWN_HOURS = 6


def check_and_alert(
    fact: pd.DataFrame,
    dim_city: pd.DataFrame,
    dim_pollutant: pd.DataFrame,
) -> None:
    """Verifie si l'AQI depasse le seuil et envoie une alerte email si necessaire.
    Applique un cooldown de 6h pour eviter les notifications repetitives.
    """
    threshold = settings.aqi_alert_threshold

    try:
        aqi_data = fact.merge(
            dim_pollutant[["pollutant_id", "pollutant_code"]], on="pollutant_id"
        )
        aqi_data = aqi_data[aqi_data["pollutant_code"].isin(AQI_POLLUTANTS)]
        aqi_data = aqi_data[aqi_data["value"] >= threshold]

        if aqi_data.empty:
            return

        aqi_data = aqi_data.merge(
            dim_city[["city_id", "city_name"]], on="city_id"
        )

        engine = create_engine(settings.database_url)
        new_alerts = _filter_recently_alerted(aqi_data, threshold, engine)
        engine.dispose()

        if new_alerts.empty:
            return

        subject = f"Air Quality Alert - AQI >= {threshold}"
        body = _build_alert_body(new_alerts, threshold)
        _send_email(subject, body)
    except Exception:
        logger.exception("[Alert] Erreur lors de la verification des alertes")


def _filter_recently_alerted(
    data: pd.DataFrame,
    threshold: int,
    engine,
) -> pd.DataFrame:
    """Filtre les alertes deja envoyees dans les 6 dernieres heures (cooldown)."""
    rows = []
    for _, row in data.iterrows():
        query = text("""
            SELECT COUNT(*)
            FROM fact_air_quality f
            JOIN dim_date d ON f.date_id = d.date_id
            WHERE f.city_id = :city_id
              AND f.pollutant_id = :pol_id
              AND f.value >= :threshold
              AND d.full_datetime >= NOW() - INTERVAL ':hours HOUR'
        """)
        with engine.connect() as conn:
            count = conn.execute(
                query,
                {
                    "city_id": row["city_id"],
                    "pol_id": row["pollutant_id"],
                    "threshold": threshold,
                    "hours": ALERT_COOLDOWN_HOURS,
                },
            ).scalar()

        if count == 0:
            rows.append(row)

    return pd.DataFrame(rows)


def _build_alert_body(data: pd.DataFrame, threshold: int) -> str:
    """Construit le corps de l'email d'alerte au format texte."""
    lines = [f"Cities with AQI >= {threshold}:"]

    for _, row in data.iterrows():
        lines.append(
            f"  - {row['city_name']}: {row['pollutant_code']} = {row['value']}"
        )

    return "\n".join(lines)


def _send_email(subject: str, body: str) -> None:
    if not settings.email_user or not settings.email_password:
        logger.info("[Alert] Email non configure, alerte ignoree")
        return

    try:
        msg = MIMEMultipart()
        msg["From"] = settings.email_user
        msg["To"] = settings.email_recipient
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(settings.email_host, settings.email_port) as server:
            server.starttls()
            server.login(settings.email_user, settings.email_password)
            server.send_message(msg)
        logger.info("[Alert] Email envoye: %s", subject)
    except Exception:
        logger.exception("[Alert] Erreur lors de l'envoi de l'email")
