# Databricks notebook source
"""Create or verify autoscaling Lakebase synced serving tables."""
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.postgres import (
    NewPipelineSpec,
    SyncedTable,
    SyncedTableSyncedTableSpec,
    SyncedTableSyncedTableSpecSyncedTableSchedulingPolicy,
)

CATALOG = "at_10526_workspace"
SCHEMA = "influencer_engagement_fe_bar"
BRANCH = "projects/influencer-fe-bar-lb/branches/production"
POSTGRES_DATABASE = "influencer_fe_bar"

TABLES = [
    ("platinum_creator_360", "creators", "creator_id", "TRIGGERED"),
    ("platinum_campaign_360", "campaigns", "campaign_id", "TRIGGERED"),
    ("platinum_brand_360", "brands", "account_id", "SNAPSHOT"),
    ("ai_campaign_insights", "ai_insights", "campaign_id", "SNAPSHOT"),
]

workspace = WorkspaceClient()

for source, target, primary_key, mode in TABLES:
    synced_id = f"{CATALOG}.{SCHEMA}.synced_{target}"
    resource_name = f"synced_tables/{synced_id}"
    try:
        existing = workspace.postgres.get_synced_table(name=resource_name)
        print(
            f"verified {existing.name} project={existing.status.project} "
            f"pipeline_id={existing.status.pipeline_id} state={existing.status.detailed_state.value}"
        )
        continue
    except Exception as error:
        if not any(marker in str(error).lower() for marker in ("not found", "not_found", "404")):
            raise

    spec = SyncedTableSyncedTableSpec(
        source_table_full_name=f"{CATALOG}.{SCHEMA}.{source}",
        primary_key_columns=[primary_key],
        scheduling_policy=SyncedTableSyncedTableSpecSyncedTableSchedulingPolicy(mode),
        branch=BRANCH,
        postgres_database=POSTGRES_DATABASE,
        create_database_objects_if_missing=True,
        new_pipeline_spec=NewPipelineSpec(storage_catalog=CATALOG, storage_schema=SCHEMA),
    )
    operation = workspace.postgres.create_synced_table(
        synced_table=SyncedTable(spec=spec),
        synced_table_id=synced_id,
    )
    created = operation.result()
    print(f"created {created.name} project={created.status.project} pipeline_id={created.status.pipeline_id}")
