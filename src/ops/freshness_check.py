# Databricks notebook source
# MAGIC %md
# MAGIC # Freshness gate
# MAGIC
# MAGIC Fails the run unless every Lakebase mirror (a) has the same row count as its Unity Catalog
# MAGIC source and (b) carries a timestamp within the SLA of the source's newest timestamp.

# COMMAND ----------

dbutils.widgets.text("catalog", "at_workspace_102126")
dbutils.widgets.text("schema", "renewal_radar")
dbutils.widgets.text("endpoint", "projects/renewal-radar-lb/branches/production/endpoints/primary")
dbutils.widgets.text("pg_database", "databricks_postgres")
dbutils.widgets.text("sla_seconds", "300")
CATALOG, SCHEMA = dbutils.widgets.get("catalog"), dbutils.widgets.get("schema")
ENDPOINT, PG_DB, SLA = dbutils.widgets.get("endpoint"), dbutils.widgets.get("pg_database"), int(dbutils.widgets.get("sla_seconds"))

def record_run(task: str, payload: dict) -> None:
    """Persist this task's result to the governed run_log table and return it as the task exit value."""
    import json as _json
    from datetime import datetime as _dt, timezone as _tz
    body = _json.dumps(payload, sort_keys=True, default=str)
    spark.createDataFrame([(task, _dt.now(_tz.utc).isoformat(), body)], "task STRING, recorded_at STRING, payload STRING") \
        .write.mode("append").saveAsTable(f"{CATALOG}.{SCHEMA}.run_log")
    dbutils.notebook.exit(body)

# (source, mirror, timestamp column or None for count-only)
PAIRS = [
    ("platinum_creators", "synced_creators", None),
    ("platinum_campaigns", "synced_campaigns", None),
    ("platinum_campaign_roi", "synced_campaign_roi", None),
    ("brand_radar_serving", "synced_brand_radar", "scored_at"),
    ("campaign_actions_serving", "synced_campaign_actions", "generated_at"),
]

# COMMAND ----------

from datetime import timezone

import psycopg
from databricks.sdk import WorkspaceClient


def utc(ts):
    """Spark returns naive timestamps, Postgres aware ones; compare both as UTC."""
    return ts.replace(tzinfo=timezone.utc) if ts is not None and ts.tzinfo is None else ts.astimezone(timezone.utc) if ts else None


w = WorkspaceClient()
host = w.postgres.get_endpoint(name=ENDPOINT).status.hosts.host
user = w.current_user.me().user_name
token = w.postgres.generate_database_credential(endpoint=ENDPOINT).token

failures, results = [], []
with psycopg.connect(f"host={host} dbname={PG_DB} user={user} password={token} sslmode=require") as conn, conn.cursor() as cur:
    for src, mirror, ts in PAIRS:
        src_n = spark.table(f"{CATALOG}.{SCHEMA}.{src}").count()
        cur.execute(f'SELECT COUNT(*) FROM "{SCHEMA}"."{mirror}"')
        mir_n = cur.fetchone()[0]
        lag = None
        if ts:
            src_ts = spark.sql(f"SELECT MAX({ts}) FROM {CATALOG}.{SCHEMA}.{src}").first()[0]
            cur.execute(f'SELECT MAX({ts}) FROM "{SCHEMA}"."{mirror}"')
            mir_ts = cur.fetchone()[0]
            src_ts, mir_ts = utc(src_ts), utc(mir_ts)
            lag = abs((src_ts - mir_ts).total_seconds()) if src_ts and mir_ts else None
        ok = src_n == mir_n and (lag is None or lag <= SLA)
        print(f"{mirror:<26} source_rows={src_n:<7} lakebase_rows={mir_n:<7} lag_s={lag} {'OK' if ok else 'FAIL'}")
        results.append({"mirror": mirror, "source_rows": src_n, "lakebase_rows": mir_n, "lag_s": lag, "ok": ok})
        if not ok:
            failures.append(mirror)

assert not failures, f"freshness check failed for {failures}"
print(f"FRESHNESS_OK sla_seconds={SLA} mirrors={len(PAIRS)}")

# COMMAND ----------

record_run("freshness_check", {"sla_seconds": SLA, "mirrors": results})
