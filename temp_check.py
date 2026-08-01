import sqlite3
c = sqlite3.connect('/home/ubuntu/AirQualityIndice/airflow/airflow.db')
rows = c.execute("SELECT dag_id, state FROM dag_run ORDER BY start_date DESC LIMIT 3").fetchall()
print("dag_runs:", rows)
rows = c.execute("SELECT task_id, state FROM task_instance ORDER BY start_date DESC LIMIT 5").fetchall()
print("tasks:", rows)
