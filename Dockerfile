FROM apache/airflow:3.3.0

COPY requirements.txt /
RUN pip install --no-cache-dir "apache-airflow==${AIRFLOW_VERSION}" -r /requirements.txt

COPY aqi_config/ /opt/airflow/aqi_config/
COPY src/ /opt/airflow/src/
COPY data/ /opt/airflow/data/