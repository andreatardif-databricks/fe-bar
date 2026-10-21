# Databricks notebook source
"""Create native MLflow UC trace tables and the app OTEL log table."""
import os
import time

import mlflow
from databricks.sdk import WorkspaceClient
from mlflow.entities import UnityCatalog

CATALOG = "at_10526_workspace"
SCHEMA = "influencer_engagement_fe_bar"
WAREHOUSE_ID = "70662a24f8050a48"
EXPERIMENT_NAME = "/Shared/traackr-influencer-recommendations"
APP_NAME = "influencer-fe-bar"

mlflow.set_tracking_uri("databricks")
os.environ["MLFLOW_TRACING_SQL_WAREHOUSE_ID"] = WAREHOUSE_ID

trace_location = UnityCatalog(
    catalog_name=CATALOG,
    schema_name=SCHEMA,
    table_prefix="traackr_mlflow",
)
experiment = mlflow.set_experiment(
    experiment_name=EXPERIMENT_NAME,
    trace_location=trace_location,
)
experiment_id = experiment.experiment_id


@mlflow.trace(name="observability_setup", span_type="CHAIN")
def seed_trace() -> dict:
    return {"status": "UC table-prefix tracing active", "experiment_id": experiment_id}


print(seed_trace())
mlflow.flush_trace_async_logging()
print(f"MLflow traces configured for {CATALOG}.{SCHEMA}.traackr_mlflow_*")

workspace = WorkspaceClient()


def execute(sql: str):
    response = workspace.statement_execution.execute_statement(
        warehouse_id=WAREHOUSE_ID,
        statement=sql,
        wait_timeout="50s",
    )
    while response.status.state.value in ("PENDING", "RUNNING"):
        time.sleep(2)
        response = workspace.statement_execution.get_statement(response.statement_id)
    if response.status.state.value != "SUCCEEDED":
        raise RuntimeError(response.status.error)
    print(f"SUCCEEDED statement_id={response.statement_id}")
    return response


execute(
    f"""
    CREATE TABLE IF NOT EXISTS {CATALOG}.{SCHEMA}.app_otel_logs (
      event_timestamp TIMESTAMP,
      trace_id STRING,
      span_id STRING,
      severity_text STRING,
      body STRING,
      service_name STRING,
      route STRING,
      http_method STRING,
      http_status_code INT,
      duration_ms DOUBLE,
      attributes MAP<STRING, STRING>
    )
    COMMENT 'OpenTelemetry-shaped request and model invocation logs from the Traackr Databricks App'
    """
)

app = workspace.apps.get(APP_NAME)
principal = app.service_principal_client_id
tables_response = execute(
    f"""
    SELECT table_name, table_type
    FROM {CATALOG}.information_schema.tables
    WHERE table_schema = '{SCHEMA}'
      AND (table_name LIKE 'traackr_mlflow%' OR table_name = 'app_otel_logs')
    ORDER BY table_name
    """
)
table_rows = tables_response.result.data_array or []
table_names = [row[0] for row in table_rows]
if "app_otel_logs" not in table_names or not any(name.startswith("traackr_mlflow") for name in table_names):
    raise RuntimeError(f"Expected observability tables were not created: {table_names}")
for table, table_type in table_rows:
    privileges = "SELECT" if table_type == "VIEW" else "MODIFY, SELECT"
    execute(f"GRANT {privileges} ON TABLE {CATALOG}.{SCHEMA}.{table} TO `{principal}`")

print(f"Granted app service principal {principal} required access on UC observability objects: {table_names}")
