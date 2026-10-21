# Databricks notebook source
# MAGIC %md
# MAGIC # Sync serving tables into Lakebase Autoscaling
# MAGIC
# MAGIC Creates any missing synced table, then triggers an incremental refresh and waits until every
# MAGIC one reports `ONLINE_NO_PENDING_UPDATE`. Runs only after the pipeline, scoring and
# MAGIC recommendation tasks succeed, so Lakebase never serves a half-updated state.

# COMMAND ----------

dbutils.widgets.text("catalog", "at_workspace_102126")
dbutils.widgets.text("schema", "renewal_radar")
dbutils.widgets.text("branch", "projects/renewal-radar-lb/branches/production")
dbutils.widgets.text("pg_database", "databricks_postgres")
CATALOG, SCHEMA = dbutils.widgets.get("catalog"), dbutils.widgets.get("schema")
BRANCH, PG_DB = dbutils.widgets.get("branch"), dbutils.widgets.get("pg_database")

# (source table, synced name, primary key, scheduling policy)
SERVING = [
    ("platinum_creators", "synced_creators", "creator_id", "TRIGGERED"),
    ("platinum_campaigns", "synced_campaigns", "campaign_id", "TRIGGERED"),
    ("platinum_campaign_roi", "synced_campaign_roi", "campaign_id", "SNAPSHOT"),
    ("brand_radar_serving", "synced_brand_radar", "account_id", "SNAPSHOT"),
    ("campaign_actions_serving", "synced_campaign_actions", "campaign_id", "SNAPSHOT"),
]

# COMMAND ----------

import time

from databricks.sdk import WorkspaceClient
from databricks.sdk.errors import NotFound
from databricks.sdk.service.postgres import (
    NewPipelineSpec, SyncedTable, SyncedTableSyncedTableSpec, SyncedTableSyncedTableSpecSyncedTableSchedulingPolicy as Policy)

w = WorkspaceClient()


def synced_name(short: str) -> str:
    return f"synced_tables/{CATALOG}.{SCHEMA}.{short}"


for source, short, pk, policy in SERVING:
    try:
        w.postgres.get_synced_table(name=synced_name(short))
        print(f"exists   {short}")
    except NotFound:
        spec = SyncedTableSyncedTableSpec(
            source_table_full_name=f"{CATALOG}.{SCHEMA}.{source}", primary_key_columns=[pk],
            scheduling_policy=Policy(policy), branch=BRANCH, postgres_database=PG_DB,
            create_database_objects_if_missing=True,
            new_pipeline_spec=NewPipelineSpec(storage_catalog=CATALOG, storage_schema=SCHEMA))
        w.postgres.create_synced_table(synced_table=SyncedTable(spec=spec), synced_table_id=f"{CATALOG}.{SCHEMA}.{short}")
        print(f"created  {short}")  # readiness is awaited by the polling loop below

# COMMAND ----------

# Trigger a refresh of every synced table, then poll until all are online with nothing pending.
started = time.time()
for _, short, _, _ in SERVING:
    pid = w.postgres.get_synced_table(name=synced_name(short)).status.pipeline_id
    try:
        w.pipelines.start_update(pipeline_id=pid, full_refresh=False)
        print(f"refresh  {short} pipeline={pid}")
    except Exception as err:  # an update may already be running for a freshly created table
        print(f"refresh  {short}: {str(err)[:120]}")

deadline = time.time() + 40 * 60
while True:
    states = {short: w.postgres.get_synced_table(name=synced_name(short)).status.detailed_state.value for _, short, _, _ in SERVING}
    print(time.strftime("%H:%M:%S"), states)
    if all(s.endswith("ONLINE_NO_PENDING_UPDATE") for s in states.values()):
        break
    if time.time() > deadline:
        raise RuntimeError(f"synced tables not online: {states}")
    time.sleep(20)

print(f"SYNC_COMPLETE tables={len(SERVING)} elapsed_s={time.time() - started:.0f}")

# COMMAND ----------

import json as _j
print(_j.dumps({"task": "sync_lakebase", "tables": {short: w.postgres.get_synced_table(name=synced_name(short)).status.detailed_state.value for _, short, _, _ in SERVING}, "elapsed_s": round(time.time() - started)}))
