# Databricks notebook source
# MAGIC %md
# MAGIC # Publish the API catalog
# MAGIC
# MAGIC The Genie space answers "which endpoint shows X?" from this governed table, so the answer
# MAGIC and the deployed routes cannot drift apart: both are edited in this one place.

# COMMAND ----------

dbutils.widgets.text("catalog", "at_workspace_102126")
dbutils.widgets.text("schema", "renewal_radar")
FQ = f"{dbutils.widgets.get('catalog')}.{dbutils.widgets.get('schema')}"

# COMMAND ----------

spark.sql(f"""
CREATE OR REPLACE TABLE {FQ}.api_endpoint_catalog
COMMENT 'Routes exposed by the Renewal Radar API; Genie answers endpoint questions from this table'
AS SELECT * FROM VALUES
  ('GET',  '/v1/brands/{{account_id}}/renewal-health',    'Modelled renewal risk score, band and the drivers behind it',        'X-Api-Key (brand or portfolio)'),
  ('GET',  '/v1/brands/{{account_id}}/campaigns',         'Campaign spend, revenue and ROI for one brand',                      'X-Api-Key (brand or portfolio)'),
  ('GET',  '/v1/brands/{{account_id}}/recommendations',   'Persisted ai_gen actions for underperforming campaigns',             'X-Api-Key (brand or portfolio)'),
  ('GET',  '/v1/portfolio/risk',                          'All brands ranked by modelled renewal risk',                         'X-Api-Key (portfolio only)'),
  ('GET',  '/v1/portfolio/actions',                       'Largest persisted ai_gen actions across all brands',                 'X-Api-Key (portfolio only)'),
  ('GET',  '/v1/portfolio/summary',                       'ARR at risk, reallocation opportunity and ROI by region',            'X-Api-Key (portfolio only)'),
  ('GET',  '/v1/creators',                                'Creator roster filterable by tier and region',                       'X-Api-Key'),
  ('POST', '/v1/campaigns/explain',                       'Live foundation-model explanation for a flagged campaign',           'X-Api-Key'),
  ('GET',  '/v1/pipeline/last-run',                       'Task-level timings of the latest orchestration run',                 'X-Api-Key (portfolio only)')
AS endpoints(method, path, purpose, authentication)
""")
print("API_CATALOG_PUBLISHED rows=", spark.table(f"{FQ}.api_endpoint_catalog").count())
