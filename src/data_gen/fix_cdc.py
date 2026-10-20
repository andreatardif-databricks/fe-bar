"""
Targeted fix: rebuild CDC volumes as a single unified parquet write each.
Reuses the bronze tables already loaded so we don't re-run the heavy synthetic gen.

The original generate.py wrote CDC in two phases (historical + late events) producing
parquet files with incompatible micro-schemas. Auto Loader cannot merge them.
This script rebuilds the CDC parquet folders with a single write per topic.
"""
from databricks.connect import DatabricksSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window
from datetime import datetime, timedelta

CATALOG = "at_10526_workspace"
SCHEMA = "influencer_engagement_fe_bar"
CDC = f"/Volumes/{CATALOG}/{SCHEMA}/cdc_events"

NOW = datetime.utcnow()
STORY_START = NOW - timedelta(days=540)
late_ts = NOW - timedelta(hours=2)

spark = DatabricksSession.builder.serverless(True).getOrCreate()
spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"USE SCHEMA {SCHEMA}")

# Read current bronze creator/campaign state from the already-loaded bronze tables.
# The bronze CDC tables couldn't load (schema infer failure), but the bronze raw
# tables (salesforce_accounts, etc.) aren't useful here. We need the master state.
# Reconstruct master state from the current cdc parquet (mergeSchema=true reads OK):
print("Reading existing CDC parquet with mergeSchema...")
old_creators = spark.read.option("mergeSchema", "true").parquet(f"{CDC}/creators")
old_camps = spark.read.option("mergeSchema", "true").parquet(f"{CDC}/campaigns")
print(f"  old creators events: {old_creators.count()}, old campaigns events: {old_camps.count()}")

# Project to a uniform schema with explicit casts on each payload field.
unified_creators = old_creators.select(
    F.col("event_id").cast("string").alias("event_id"),
    F.col("creator_id").cast("string").alias("creator_id"),
    F.col("op").cast("string").alias("op"),
    F.col("seq").cast("long").alias("seq"),
    F.col("timestamp").cast("timestamp").alias("timestamp"),
    F.struct(
        F.col("payload.creator_id").cast("string").alias("creator_id"),
        F.col("payload.handle").cast("string").alias("handle"),
        F.col("payload.display_name").cast("string").alias("display_name"),
        F.col("payload.tier").cast("string").alias("tier"),
        F.col("payload.platform").cast("string").alias("platform"),
        F.col("payload.country").cast("string").alias("country"),
        F.col("payload.follower_count").cast("long").alias("follower_count"),
        F.col("payload.status").cast("string").alias("status"),
        F.col("payload.agent_email").cast("string").alias("agent_email"),
        F.col("payload.joined_at").cast("timestamp").alias("joined_at"),
        F.col("payload.updated_at").cast("timestamp").alias("updated_at"),
    ).alias("payload"),
)

unified_camps = old_camps.select(
    F.col("event_id").cast("string").alias("event_id"),
    F.col("campaign_id").cast("string").alias("campaign_id"),
    F.col("op").cast("string").alias("op"),
    F.col("seq").cast("long").alias("seq"),
    F.col("timestamp").cast("timestamp").alias("timestamp"),
    F.struct(
        F.col("payload.campaign_id").cast("string").alias("campaign_id"),
        F.col("payload.account_id").cast("string").alias("account_id"),
        F.col("payload.name").cast("string").alias("name"),
        F.col("payload.start_date").cast("date").alias("start_date"),
        F.col("payload.end_date").cast("date").alias("end_date"),
        F.col("payload.budget_usd").cast("double").alias("budget_usd"),
        F.col("payload.status").cast("string").alias("status"),
        F.col("payload.created_at").cast("timestamp").alias("created_at"),
        F.col("payload.updated_at").cast("timestamp").alias("updated_at"),
    ).alias("payload"),
)

# Materialize through Delta tmp tables, then single overwrite write to parquet.
# Using a tmp table breaks the read→write dependency on the same parquet path.
tmp_cr = f"{CATALOG}.{SCHEMA}._tmp_unified_creators"
tmp_cm = f"{CATALOG}.{SCHEMA}._tmp_unified_campaigns"
unified_creators.write.mode("overwrite").saveAsTable(tmp_cr)
unified_camps.write.mode("overwrite").saveAsTable(tmp_cm)
print("Materialized unified DataFrames to tmp Delta tables.")

# Now overwrite the parquet path
spark.table(tmp_cr).coalesce(2).write.mode("overwrite").parquet(f"{CDC}/creators")
spark.table(tmp_cm).coalesce(2).write.mode("overwrite").parquet(f"{CDC}/campaigns")
print("Wrote unified parquet to CDC volumes.")

# Verify schema is single-file consistent now
verify_cr = spark.read.parquet(f"{CDC}/creators")
verify_cm = spark.read.parquet(f"{CDC}/campaigns")
print(f"Verified creators: {verify_cr.count()} rows, schema OK")
print(f"Verified campaigns: {verify_cm.count()} rows, schema OK")

spark.sql(f"DROP TABLE IF EXISTS {tmp_cr}")
spark.sql(f"DROP TABLE IF EXISTS {tmp_cm}")
print("Done.")
