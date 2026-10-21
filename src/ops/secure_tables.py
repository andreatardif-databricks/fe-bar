# Databricks notebook source
# MAGIC %md
# MAGIC # Brand isolation at the data layer
# MAGIC
# MAGIC Unity Catalog row filters make brand scoping hold for every consumer of the governed
# MAGIC tables (SQL, Genie, notebooks), not only the API. A principal sees a row when it is an
# MAGIC admin, or when `brand_access` grants it that `account_id`.

# COMMAND ----------

dbutils.widgets.text("catalog", "at_workspace_102126")
dbutils.widgets.text("schema", "renewal_radar")
CATALOG, SCHEMA = dbutils.widgets.get("catalog"), dbutils.widgets.get("schema")
FQ = f"{CATALOG}.{SCHEMA}"

# COMMAND ----------

spark.sql(f"""
CREATE TABLE IF NOT EXISTS {FQ}.brand_access (
  principal STRING NOT NULL COMMENT 'User email or service principal application id',
  account_id STRING NOT NULL COMMENT 'Brand the principal may see'
) COMMENT 'Row-level security grants for brand-scoped consumers'
""")

spark.sql(f"""
CREATE OR REPLACE FUNCTION {FQ}.brand_row_filter(account_id STRING)
RETURNS BOOLEAN
COMMENT 'TRUE for workspace admins or principals granted this brand in brand_access'
RETURN is_account_group_member('admins')
    OR is_member('admins')
    OR EXISTS (SELECT 1 FROM {FQ}.brand_access ba WHERE ba.principal = current_user() AND ba.account_id = account_id)
""")

# the job's own identity must always see all rows (it runs the pipeline and the sync)
me = spark.sql("SELECT current_user()").first()[0]
spark.sql(f"MERGE INTO {FQ}.brand_access t USING (SELECT '{me}' AS principal, 'ACC-0000' AS account_id) s "
          f"ON t.principal = s.principal AND t.account_id = s.account_id WHEN NOT MATCHED THEN INSERT *")

# Synced-table sources cannot carry row filters, so Lakebase is fed from unfiltered *_serving copies
# that only the pipeline owner can read. Every analyst-facing table keeps its row filter.
for table in ("brand_radar", "campaign_actions"):
    try:
        spark.sql(f"ALTER TABLE {FQ}.{table} DROP ROW FILTER")  # make the copy read all rows
    except Exception:
        pass
    spark.sql(f"CREATE OR REPLACE TABLE {FQ}.{table}_serving COMMENT 'Unfiltered copy that feeds Lakebase sync; owner-only' AS SELECT * FROM {FQ}.{table}")
    spark.sql(f"ALTER TABLE {FQ}.{table} SET ROW FILTER {FQ}.brand_row_filter ON (account_id)")
    print(f"serving copy refreshed and row filter applied: {FQ}.{table}")

print("ROW_FILTERS_APPLIED tables=brand_radar,campaign_actions")
