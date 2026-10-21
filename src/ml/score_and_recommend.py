# Databricks notebook source
# MAGIC %md
# MAGIC # Score brands, generate grounded recommendations, size the opportunity
# MAGIC
# MAGIC 1. Score every brand with the registered `champion` renewal-risk model -> `brand_radar`.
# MAGIC 2. For the highest-value underperforming campaigns, call `ai_gen` with the campaign's
# MAGIC    metrics **and the owning brand's model risk score** -> `campaign_actions`.
# MAGIC 3. Roll the bottom-up numbers into `value_summary` so the deck quotes governed rows.

# COMMAND ----------

dbutils.widgets.text("catalog", "at_workspace_102126")
dbutils.widgets.text("schema", "renewal_radar")
CATALOG, SCHEMA = dbutils.widgets.get("catalog"), dbutils.widgets.get("schema")
FQ = f"{CATALOG}.{SCHEMA}"
MODEL_URI = f"models:/{FQ}.renewal_risk@champion"

def record_run(task: str, payload: dict) -> None:
    """Persist this task's result to the governed run_log table and return it as the task exit value."""
    import json as _json
    from datetime import datetime as _dt, timezone as _tz
    body = _json.dumps(payload, sort_keys=True, default=str)
    spark.createDataFrame([(task, _dt.now(_tz.utc).isoformat(), body)], "task STRING, recorded_at STRING, payload STRING") \
        .write.mode("append").saveAsTable(f"{CATALOG}.{SCHEMA}.run_log")
    dbutils.notebook.exit(body)

# COMMAND ----------

import mlflow
import pandas as pd

mlflow.set_registry_uri("databricks-uc")
model = mlflow.sklearn.load_model(MODEL_URI)

features = spark.table(f"{FQ}.gold_brand_features").toPandas()
cols = ["avg_roi_180d", "active_campaigns", "revenue_trend_90d", "late_invoice_rate", "region", "tier"]
features["renewal_risk_score"] = model.predict_proba(features[cols])[:, 1].round(4)
features["risk_band"] = pd.cut(features.renewal_risk_score, [-0.01, 0.40, 0.65, 1.01], labels=["low", "medium", "high"]).astype(str)
features["scored_at"] = pd.Timestamp.now(tz="UTC")
features["model_uri"] = MODEL_URI

(spark.createDataFrame(features)
    .write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{FQ}.brand_radar"))
spark.sql(f"COMMENT ON TABLE {FQ}.brand_radar IS 'Brand renewal-risk scores from the UC-registered champion model'")
print(features.risk_band.value_counts().to_dict())

# COMMAND ----------
# The brand risk score is part of the prompt, so the generated action reflects how much the
# relationship is at risk and not only the campaign's current-period ROI.

spark.sql(f"""
CREATE OR REPLACE TABLE {FQ}.campaign_actions
COMMENT 'ai_gen campaign actions grounded in campaign metrics and the brand renewal-risk score'
AS
WITH top_gap AS (
  SELECT o.*, r.renewal_risk_score, r.risk_band, r.arr_usd, r.tier,
         ROW_NUMBER() OVER (ORDER BY o.incremental_revenue_usd DESC) AS rk
  FROM {FQ}.gold_reallocation_opportunity o
  JOIN {FQ}.brand_radar r USING (account_id)
)
SELECT campaign_id, account_id, brand_name, region, campaign_name,
       ROUND(spend_90d_usd, 2) AS spend_90d_usd, ROUND(roi_90d, 3) AS roi_90d,
       ROUND(benchmark_roi, 3) AS benchmark_roi, ROUND(incremental_revenue_usd, 2) AS incremental_revenue_usd,
       renewal_risk_score, risk_band,
       ai_gen(concat(
         'You advise a creator-marketing platform account team. Using only these facts, write one ',
         'specific action under 40 words. If the renewal risk is high, make retention the priority. ',
         'Campaign: ', campaign_name, '. Region: ', region, '. 90-day spend USD: ', CAST(ROUND(spend_90d_usd) AS STRING),
         '. 90-day ROI: ', CAST(ROUND(roi_90d, 2) AS STRING), ' versus a regional benchmark of ',
         CAST(ROUND(benchmark_roi, 2) AS STRING), '. Brand renewal risk: ', risk_band, ' (',
         CAST(ROUND(renewal_risk_score * 100) AS STRING), '% modelled churn probability), ARR USD ',
         CAST(ROUND(arr_usd) AS STRING), '.')) AS recommendation,
       current_timestamp() AS generated_at,
       'ai_gen' AS generator
FROM top_gap WHERE rk <= 25
""")
print(spark.table(f"{FQ}.campaign_actions").select("campaign_id", "risk_band", "recommendation").limit(3).toPandas().to_string())

# COMMAND ----------

spark.sql(f"""
CREATE OR REPLACE TABLE {FQ}.value_summary
COMMENT 'Bottom-up value: every figure traces to governed rows'
AS
SELECT 'underperforming_campaigns' AS metric, CAST(COUNT(*) AS DOUBLE) AS value, 'count' AS unit,
       'ROI<1.0 campaigns active in last 90 days with >$5K 90d spend' AS definition
FROM {FQ}.gold_reallocation_opportunity
UNION ALL
SELECT 'trailing_90d_spend_on_underperformers', SUM(spend_90d_usd), 'usd', 'Sum of spend_90d_usd' FROM {FQ}.gold_reallocation_opportunity
UNION ALL
SELECT 'annual_spend_shifted', SUM(annual_spend_shifted_usd), 'usd', '30% of 90d spend x4' FROM {FQ}.gold_reallocation_opportunity
UNION ALL
SELECT 'incremental_attributed_revenue', SUM(incremental_revenue_usd), 'usd', 'shifted spend x (regional benchmark ROI - campaign ROI)' FROM {FQ}.gold_reallocation_opportunity
UNION ALL
SELECT 'arr_in_high_risk_brands', SUM(arr_usd), 'usd', 'ARR of brands scored high renewal risk' FROM {FQ}.brand_radar WHERE risk_band = 'high'
UNION ALL
SELECT 'high_risk_brands', CAST(COUNT(*) AS DOUBLE), 'count', 'Brands scored high renewal risk' FROM {FQ}.brand_radar WHERE risk_band = 'high'
""")
display(spark.table(f"{FQ}.value_summary"))
print("VALUE_SUMMARY " + str({r.metric: round(r.value, 2) for r in spark.table(f"{FQ}.value_summary").collect()}))

# COMMAND ----------

rows = {r.metric: round(r.value, 2) for r in spark.table(f"{FQ}.value_summary").collect()}
bands = features.risk_band.value_counts().to_dict()
record_run("score_and_recommend", {"model_uri": MODEL_URI, "risk_bands": bands, "value_summary": rows, "actions": spark.table(f"{FQ}.campaign_actions").count()})
