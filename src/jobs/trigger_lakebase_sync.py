# Databricks notebook source
"""Trigger refresh of all Lakebase serving tables and wait for completion."""
import time
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()

CATALOG = "at_10526_workspace"
SCHEMA = "influencer_engagement_fe_bar"
TABLES = ["synced_creators", "synced_campaigns", "synced_brands", "synced_ai_insights"]

print("Triggering refresh on synced tables...")
for t in TABLES:
    name = f"{CATALOG}.{SCHEMA}.{t}"
    st = w.postgres.get_synced_table(name=f"synced_tables/{name}")
    pipeline_id = st.status.pipeline_id if st.status else None
    if pipeline_id:
        try:
            w.pipelines.start_update(pipeline_id=pipeline_id, full_refresh=False)
            print(f"  {t}: triggered pipeline {pipeline_id}")
        except Exception as e:
            print(f"  {t}: trigger error: {e}")
    else:
        print(f"  {t}: no pipeline id (skipping)")

print("\nWaiting for syncs to complete...")
for _ in range(60):
    all_ok = True
    states = []
    for t in TABLES:
        name = f"{CATALOG}.{SCHEMA}.{t}"
        st = w.postgres.get_synced_table(name=f"synced_tables/{name}")
        s = st.status
        ds = (s.detailed_state.value if s and s.detailed_state else "?")
        states.append(f"{t}={ds}")
        if "ONLINE_NO_PENDING_UPDATE" not in ds:
            all_ok = False
    print(time.strftime("%H:%M:%S"), " | ".join(states))
    if all_ok:
        print("All synced tables online.")
        break
    time.sleep(15)
else:
    raise RuntimeError("Timed out waiting for synced tables.")
