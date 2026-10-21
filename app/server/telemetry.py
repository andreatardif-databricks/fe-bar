"""MLflow tracing and governed OpenTelemetry-shaped application logs."""
from __future__ import annotations

import json
import os
import time
import uuid

import mlflow
from databricks.sdk import WorkspaceClient
from mlflow.entities import UnityCatalog

CATALOG = os.environ.get("UC_CATALOG", "at_10526_workspace")
SCHEMA = os.environ.get("UC_SCHEMA", "influencer_engagement_fe_bar")
WAREHOUSE_ID = os.environ.get("WAREHOUSE_ID", "70662a24f8050a48")
EXPERIMENT_NAME = "/Shared/traackr-influencer-recommendations"


def configure_tracing() -> None:
    mlflow.set_tracking_uri("databricks")
    mlflow.set_experiment(
        experiment_name=EXPERIMENT_NAME,
        trace_location=UnityCatalog(
            catalog_name=CATALOG,
            schema_name=SCHEMA,
            table_prefix="traackr_mlflow",
        ),
    )


def _sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def persist_otel_log(
    *,
    trace_id: str,
    span_id: str,
    body: str,
    route: str,
    method: str,
    status_code: int,
    duration_ms: float,
    attributes: dict[str, str],
) -> None:
    workspace = WorkspaceClient()
    attributes_json = json.dumps(attributes, sort_keys=True)
    statement = f"""
    INSERT INTO {CATALOG}.{SCHEMA}.app_otel_logs
    SELECT current_timestamp(), {_sql_string(trace_id)}, {_sql_string(span_id)},
           'INFO', {_sql_string(body)}, 'influencer-fe-bar', {_sql_string(route)},
           {_sql_string(method)}, {int(status_code)}, {float(duration_ms)},
           from_json({_sql_string(attributes_json)}, 'MAP<STRING,STRING>')
    """
    workspace.statement_execution.execute_statement(
        warehouse_id=WAREHOUSE_ID,
        statement=statement,
        wait_timeout="30s",
    )


def new_trace_context() -> tuple[str, str, float]:
    return uuid.uuid4().hex, uuid.uuid4().hex[:16], time.perf_counter()
