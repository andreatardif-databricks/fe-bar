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
# Every brand gets at least one action, chosen by its situation:
#   fix        it has an underperforming campaign (the reallocation opportunity)
#   scale      it is healthy and active: build on its best campaign
#   reactivate it has been quiet for 90 days: a retention play, not a campaign tweak
# The brand's modelled churn probability is part of every prompt, so a campaign on a brand at 95%
# risk is treated differently from the same campaign on a brand at 5%.

spark.sql(f"""
CREATE OR REPLACE TABLE {FQ}.campaign_actions
COMMENT 'ai_gen actions, at least one per brand, grounded in campaign metrics and the brand renewal-risk score'
AS
WITH benchmark AS (
  SELECT region, PERCENTILE(roi_90d, 0.5) AS benchmark_roi
  FROM {FQ}.gold_campaign_performance WHERE roi_90d >= 1.0 AND spend_90d_usd > 1000 GROUP BY region
), fixes AS (
  SELECT campaign_id, account_id, 'fix' AS action_type, spend_90d_usd, roi_90d, benchmark_roi,
         incremental_revenue_usd, 0.0 AS scale_upside_usd,
         ROW_NUMBER() OVER (PARTITION BY account_id ORDER BY incremental_revenue_usd DESC) AS rk
  FROM {FQ}.gold_reallocation_opportunity
), best AS (
  SELECT p.campaign_id, p.account_id,
         CASE WHEN p.last_activity_date >= date_sub(current_date(), 90) THEN 'scale' ELSE 'reactivate' END AS action_type,
         COALESCE(p.spend_90d_usd, 0) AS spend_90d_usd, COALESCE(p.roi_90d, p.roi) AS roi_90d, b.benchmark_roi,
         0.0 AS incremental_revenue_usd,
         CASE WHEN p.last_activity_date >= date_sub(current_date(), 90)
              THEN 0.20 * COALESCE(p.spend_90d_usd, 0) * 4 * COALESCE(p.roi_90d, p.roi) ELSE 0.0 END AS scale_upside_usd,
         -- recent campaigns sort first, so a brand is only 'reactivate' when NONE of its campaigns are recent
         ROW_NUMBER() OVER (PARTITION BY p.account_id
                            ORDER BY (p.last_activity_date >= date_sub(current_date(), 90)) DESC,
                                     COALESCE(p.roi_90d, p.roi) DESC NULLS LAST, p.spend_usd DESC) AS rk
  FROM {FQ}.gold_campaign_performance p LEFT JOIN benchmark b USING (region)
  WHERE p.account_id NOT IN (SELECT account_id FROM {FQ}.gold_reallocation_opportunity)
), picked AS (
  SELECT * FROM fixes WHERE rk <= 3
  UNION ALL
  SELECT campaign_id, account_id, action_type, spend_90d_usd, roi_90d, benchmark_roi, incremental_revenue_usd, scale_upside_usd, rk
  FROM best WHERE rk = 1
), enriched AS (
  SELECT pk.*, p.brand_name, p.region, p.campaign_name, r.renewal_risk_score, r.risk_band, r.arr_usd
  FROM picked pk
  JOIN {FQ}.gold_campaign_performance p USING (campaign_id)
  JOIN {FQ}.brand_radar r ON r.account_id = pk.account_id
)
SELECT campaign_id, account_id, brand_name, region, campaign_name, action_type,
       ROUND(spend_90d_usd, 2) AS spend_90d_usd, ROUND(roi_90d, 3) AS roi_90d, ROUND(benchmark_roi, 3) AS benchmark_roi,
       ROUND(incremental_revenue_usd, 2) AS incremental_revenue_usd, ROUND(scale_upside_usd, 2) AS scale_upside_usd,
       renewal_risk_score, risk_band,
       ai_gen(concat(
         'You advise a creator-marketing platform account team. Using only these facts, write one specific action ',
         'under 40 words. ',
         CASE action_type
           WHEN 'fix' THEN 'The campaign underperforms its regional benchmark; say where to move budget. If the renewal risk is high, make retention the priority. '
           WHEN 'scale' THEN 'The campaign is performing well; say how to scale it (budget or creator mix). If the renewal risk is high, tie it to proving value before renewal. '
           ELSE 'The brand has had no campaign activity for 90 days; say how to win it back before renewal. '
         END,
         'Campaign: ', campaign_name, '. Region: ', region, '. 90-day spend USD: ', CAST(ROUND(spend_90d_usd) AS STRING),
         '. ROI: ', CAST(ROUND(roi_90d, 2) AS STRING), ' versus a regional benchmark of ', COALESCE(CAST(ROUND(benchmark_roi, 2) AS STRING), 'n/a'),
         '. Brand renewal risk: ', risk_band, ' (', CAST(ROUND(renewal_risk_score * 100) AS STRING),
         '% modelled churn probability), ARR USD ', CAST(ROUND(arr_usd) AS STRING), '.')) AS recommendation,
       current_timestamp() AS generated_at,
       'ai_gen' AS generator
FROM enriched
""")
display(spark.table(f"{FQ}.campaign_actions").groupBy("action_type").count())

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

covered = spark.table(f"{FQ}.campaign_actions").select("account_id").distinct().count()
total_brands = spark.table(f"{FQ}.brand_radar").count()
assert covered == total_brands, f"only {covered} of {total_brands} brands have an AI action"
rows = {r.metric: round(r.value, 2) for r in spark.table(f"{FQ}.value_summary").collect()}
bands = features.risk_band.value_counts().to_dict()
record_run("score_and_recommend", {"model_uri": MODEL_URI, "risk_bands": bands, "value_summary": rows, "actions": spark.table(f"{FQ}.campaign_actions").count(),
    "actions_by_type": {r.action_type: r["count"] for r in spark.table(f"{FQ}.campaign_actions").groupBy("action_type").count().collect()},
    "brands_with_an_action": spark.table(f"{FQ}.campaign_actions").select("account_id").distinct().count()})
