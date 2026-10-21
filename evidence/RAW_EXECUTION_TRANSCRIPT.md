# Raw execution transcript

Captured 2026-10-21T13:48:45+00:00 by `scripts/capture_evidence.py`. Every block below was fetched live at capture time.

## 1. Orchestration run `330757386726266`

Result: **SUCCESS** · https://dbc-37e28a61-cc0c.cloud.databricks.com/?o=7474647371758861#job/930344545327291/run/330757386726266

| task | attempt | result | seconds | depends_on |
|---|---|---|---|---|
| publish_api_catalog | 0 | SUCCESS | 23 | score_and_recommend |
| secure_tables | 0 | SUCCESS | 35 | publish_api_catalog |
| run_pipeline | 0 | SUCCESS | 94 | generate_sources |
| train_renewal_risk | 0 | SUCCESS | 82 | run_pipeline |
| sync_lakebase | 0 | SUCCESS | 123 | secure_tables |
| freshness_check | 0 | FAILED | 22 | sync_lakebase |
| freshness_check | 1 | SUCCESS | 66 | sync_lakebase |
| generate_sources | 0 | SUCCESS | 81 |  |
| score_and_recommend | 0 | SUCCESS | 60 | train_renewal_risk |

## 2. Task records (`run_log`, written by each task)

**generate_sources** at 2026-10-21T13:36:05.785806+00:00
```json
{
 "checks": {
  "churn_rate_by_region": {
   "APAC": 0.422,
   "EMEA": 0.425,
   "LATAM": 0.53,
   "NA": 0.383
  },
  "enterprise_mean_arr_usd": 401695.0,
  "follower_bands": {
   "macro": [
    1034841,
    4956811
   ],
   "micro": [
    10013,
    99985
   ],
   "mid": [
    100168,
    999954
   ],
   "nano": [
    1002,
    9992
   ]
  },
  "headline_pair_revenue_usd": 317393.91,
  "inefficient_campaign_share": 0.148,
  "latam_dec_jan_roi": 1.913,
  "na_holiday_vs_offseason_roi": [
   2.391,
   1.814
  ],
  "seeded_surge_usd": 224000.0
 },
 "first_run": true,
 "rows": {
  "accounts": 120,
  "ad_spend": 49210,
  "campaign_cdc": 925,
  "campaigns": 900,
  "creator_cdc": 3061,
  "creator_sales": 223907,
  "creators": 3000,
  "invoices": 2160,
  "renewal_history": 720,
  "social_events": 223851
 },
 "run_ts": "20261021T133521"
}
```

**train_renewal_risk** at 2026-10-21T13:39:06.806657+00:00
```json
{
 "churn_rate": 0.415,
 "holdout_auc": 0.7988,
 "model": "at_workspace_102126.renewal_radar.renewal_risk",
 "promoted": true,
 "test_rows": 180,
 "train_rows": 540,
 "version": "1"
}
```

**score_and_recommend** at 2026-10-21T13:40:09.808132+00:00
```json
{
 "actions": 25,
 "model_uri": "models:/at_workspace_102126.renewal_radar.renewal_risk@champion",
 "risk_bands": {
  "high": 46,
  "low": 50,
  "medium": 24
 },
 "value_summary": {
  "annual_spend_shifted": 888852.56,
  "arr_in_high_risk_brands": 6119000.0,
  "high_risk_brands": 46.0,
  "incremental_attributed_revenue": 1222736.64,
  "trailing_90d_spend_on_underperformers": 740710.47,
  "underperforming_campaigns": 32.0
 }
}
```

**freshness_check** at 2026-10-21T13:44:39.578716+00:00
```json
{
 "mirrors": [
  {
   "lag_s": null,
   "lakebase_rows": 2999,
   "mirror": "synced_creators",
   "ok": true,
   "source_rows": 2999
  },
  {
   "lag_s": null,
   "lakebase_rows": 900,
   "mirror": "synced_campaigns",
   "ok": true,
   "source_rows": 900
  },
  {
   "lag_s": null,
   "lakebase_rows": 900,
   "mirror": "synced_campaign_roi",
   "ok": true,
   "source_rows": 900
  },
  {
   "lag_s": 0.0,
   "lakebase_rows": 120,
   "mirror": "synced_brand_radar",
   "ok": true,
   "source_rows": 120
  },
  {
   "lag_s": 0.0,
   "lakebase_rows": 25,
   "mirror": "synced_campaign_actions",
   "ok": true,
   "source_rows": 25
  }
 ],
 "sla_seconds": 300
}
```

## 3. Governed table profile

| table_name | row_count |
|---|---|
| platinum_creators | 2999 |
| platinum_campaigns | 900 |
| brand_radar | 120 |
| campaign_actions | 25 |
| bronze_social_events | 223851 |
| bronze_creator_sales | 223907 |
| bronze_ad_spend | 49210 |
| silver_campaign_day | 49210 |
| gold_campaign_performance | 900 |
| platinum_campaign_roi | 900 |

### Bottom-up value (`value_summary`)

| metric | value | unit | definition |
|---|---|---|---|
| annual_spend_shifted | 888853.0 | usd | 30% of 90d spend x4 |
| arr_in_high_risk_brands | 6119000.0 | usd | ARR of brands scored high renewal risk |
| high_risk_brands | 46.0 | count | Brands scored high renewal risk |
| incremental_attributed_revenue | 1222737.0 | usd | shifted spend x (regional benchmark ROI - campaign ROI) |
| trailing_90d_spend_on_underperformers | 740710.0 | usd | Sum of spend_90d_usd |
| underperforming_campaigns | 32.0 | count | ROI<1.0 campaigns active in last 90 days with >$5K 90d spend |

### Renewal-risk bands (`brand_radar`)

| risk_band | brands | arr_usd | mean_score |
|---|---|---|---|
| high | 46 | 6119000.0 | 0.837 |
| low | 50 | 8416100.0 | 0.153 |
| medium | 24 | 3277100.0 | 0.521 |

### Regional seasonality (ROI by region and month, holiday peaks visible)

| region | month | roi |
|---|---|---|
| APAC | 2025-11 | 2.0 |
| APAC | 2025-12 | 2.16 |
| APAC | 2026-01 | 2.2 |
| APAC | 2026-02 | 2.64 |
| APAC | 2026-03 | 1.78 |
| APAC | 2026-04 | 1.97 |
| APAC | 2026-05 | 1.97 |
| APAC | 2026-06 | 1.81 |
| APAC | 2026-07 | 2.24 |
| APAC | 2026-08 | 2.28 |
| APAC | 2026-09 | 2.24 |
| APAC | 2026-10 | 2.01 |
| LATAM | 2025-11 | 1.44 |
| LATAM | 2025-12 | 2.21 |
| LATAM | 2026-01 | 1.7 |
| LATAM | 2026-02 | 1.8 |
| LATAM | 2026-03 | 1.29 |
| LATAM | 2026-04 | 1.58 |
| LATAM | 2026-05 | 2.12 |
| LATAM | 2026-06 | 2.49 |
| LATAM | 2026-07 | 1.63 |
| LATAM | 2026-08 | 1.56 |
| LATAM | 2026-09 | 1.81 |
| LATAM | 2026-10 | 1.65 |
| NA | 2025-11 | 2.41 |
| NA | 2025-12 | 2.37 |
| NA | 2026-01 | 1.61 |
| NA | 2026-02 | 1.74 |
| NA | 2026-03 | 1.85 |
| NA | 2026-04 | 1.87 |
| NA | 2026-05 | 1.81 |
| NA | 2026-06 | 1.77 |
| NA | 2026-07 | 1.73 |
| NA | 2026-08 | 1.85 |
| NA | 2026-09 | 1.95 |
| NA | 2026-10 | 1.9 |

## 4. `ai_gen` actions (top 5 by opportunity; the prompt includes the brand's model risk score)

| campaign | risk_band | roi_90d | benchmark | incremental_usd | recommendation |
|---|---|---|---|---|---|
| Orchard Beauty Fall Push 80 | high | 0.33 | 1.97 | 85955.0 | Prioritize retention strategies for Orchard Beauty to mitigate 95% renewal risk. |
| Prism & Co Fall Push 525 | high | 0.73 | 2.1 | 80980.0 | Prioritize retention strategies for Prism & Co Fall Push 525 to mitigate high renewal risk. |
| Tamarack & Co Fall Push 583 | high | 0.59 | 1.77 | 79698.0 | Prioritize retention strategies for Tamarack & Co to mitigate 89% renewal risk. |
| Saffron Beauty Fall Push 240 | high | 0.63 | 2.1 | 69066.0 | Prioritize retention strategies for Saffron Beauty to mitigate 80% renewal risk. |
| Nettle Athletics Fall Push 34 | low | 0.71 | 2.2 | 59132.0 | Focus on optimizing ROI for Nettle Athletics Fall Push 34 in APAC, aiming to close the gap with the regional benchmark. |

## 5. Governance

Row filter on `brand_radar` (from `DESCRIBE EXTENDED`):
```
Row Filter | `at_workspace_102126`.`renewal_radar`.`brand_row_filter` ON (account_id) | 
```

Registered model `at_workspace_102126.renewal_radar.renewal_risk` alias `champion` -> version **1**

## 6. Deployed app responses

**health (Lakebase round trip)**: `GET /v1/health` -> HTTP 200 in 376 ms
```json
{
 "status": "ok",
 "brands_served": 120,
 "lakebase_round_trip_ms": 8.0,
 "serving_endpoint": "databricks-claude-haiku-5-5"
}
```

**brand key reads its own brand**: `GET /v1/brands/ACC-0000/renewal-health` -> HTTP 200 in 354 ms
```json
{
 "account_id": "ACC-0000",
 "brand_name": "Aster Lane",
 "region": "NA",
 "tier": "enterprise",
 "arr_usd": 480000.0,
 "renewal_date": "2026-12-21",
 "renewal_risk_score": 0.0478,
 "risk_band": "low",
 "avg_roi_180d": 2.0862565426081088,
 "active_campaigns": 5,
 "revenue_trend_90d": 0.6,
 "late_invoice_rate": 0.2777777777777778,
 "scored_at": "2026-10-21T13:39:38.241213+00:00",
 "model_uri": "models:/at_workspace_102126.renewal_radar.renewal_risk@champion"
}
```

**brand key asks for ANOTHER brand -> 404**: `GET /v1/brands/ACC-0001/renewal-health` -> HTTP 404 in 355 ms
```json
{
 "detail": "brand not found"
}
```

**brand key asks for portfolio data -> 403**: `GET /v1/portfolio/summary` -> HTTP 403 in 516 ms
```json
{
 "detail": "portfolio-scoped key required"
}
```

**no key -> 401**: `GET /v1/portfolio/summary` -> HTTP 401 in 336 ms
```json
{
 "detail": "X-Api-Key header is required"
}
```

**portfolio summary**: `GET /v1/portfolio/summary` -> HTTP 200 in 344 ms
```json
{
 "risk_by_band": [
  {
   "risk_band": "high",
   "brands": 46,
   "arr_usd": 6119000.0
  },
  {
   "risk_band": "low",
   "brands": 50,
   "arr_usd": 8416100.0
  },
  {
   "risk_band": "medium",
   "brands": 24,
   "arr_usd": 3277100.0
  }
 ],
 "top_actions": {
  "campaigns": 25,
  "incremental_revenue_usd": 1122555.0,
  "spend_90d_usd": 671882.0
 },
 "roi_by_region": [
  {
   "region": "APAC",
   "roi": 1.96
  },
  {
   "region": "EMEA",
   "roi": 2.01
  },
  {
   "region": "LATAM",
   "roi": 1.69
  },
  {
   "region": "NA",
   "roi": 1.88
  }
 ]
}
```

**top persisted ai_gen actions**: `GET /v1/portfolio/actions?limit=2` -> HTTP 200 in 371 ms
```json
[
 {
  "campaign_id": "CMP-00080",
  "campaign_name": "Orchard Beauty Fall Push 80",
  "spend_90d_usd": 43609.32,
  "roi_90d": 0.326,
  "benchmark_roi": 1.969,
  "incremental_revenue_usd": 85954.74,
  "risk_band": "high",
  "renewal_risk_score": 0.947,
  "recommendation": "Prioritize retention strategies for Orchard Beauty to mitigate 95% renewal risk.",
  "generated_at": "2026-10-21T13:39:48.254099+00:00"
 },
 {
  "campaign_id": "CMP-00525",
  "campaign_name": "Prism & Co Fall Push 525",
  "spend_90d_usd": 49204.54,
  "roi_90d": 0.726,
  "benchmark_roi": 2.097,
  "incremental_revenue_usd": 80980.14,
  "risk_band": "high",
  "renewal_risk_score": 0.7134,
  "recommendation": "Prioritize retention strategies for Prism & Co Fall Push 525 to mitigate high renewal risk.",
  "generated_at": "2026-10-21T13:39:48.254099+00:00"
 }
]
```

**live foundation-model explanation**: `POST /v1/campaigns/explain` -> HTTP 200 in 3407 ms
```json
{
 "campaign_id": "CMP-00080",
 "endpoint": "databricks-claude-haiku-5-5",
 "explanation": "The 'Orchard Beauty Fall Push 80' campaign has a 90-day ROI of 0.326, far below the regional benchmark of 1.969, and the brand faces a high modelled renewal risk of 95%. Given this gap and risk, the existing action to prioritize retention strategies for Orchard Beauty needs to be treated as urgent.",
 "usage": {
  "completion_tokens": 373,
  "prompt_tokens": 124,
  "total_tokens": 497
 },
 "latency_ms": 3046
}
```

**Genie: API question -> script, no SQL**: `POST /v1/genie/ask` -> HTTP 200 in 12876 ms
```json
{
 "conversation_id": "01f1cd56383b1dbf8a5560955c64ee62",
 "message_id": "01f1cd563846178bb77c7797e516e43a",
 "status": "COMPLETED",
 "answer": "Two **GET** endpoints show renewal risk:\n- **/v1/brands/{account_id}/renewal-health** \u2014 modelled renewal risk score, band, and the drivers behind it\n- **/v1/portfolio/risk** \u2014 all brands ranked by modelled renewal risk\nAt the brand level you get the score, band, and drivers, while the portfolio endpoint gives a ranked view across brands.",
 "api_call": {
  "method": "GET",
  "path": "/v1/brands/{account_id}/renewal-health",
  "purpose": "Modelled churn probability, band and drivers",
  "script": "curl -s -X GET 'https://traackr-renewal-radar-7474647371758861.aws.databricksapps.com/v1/brands/ACC-0000/renewal-health' \\\n  -H 'X-Api-Key: rr_demo_portfolio' -H 'Accept: application/json'"
 },
 "queries": [],
 "genie_url": "https://dbc-37e28a61-cc0c.cloud.databricks.com/genie/rooms/01f1cd55187c1612a46bd87e6dcfd7da/chats/01f1cd56383b1dbf8a5560955c64ee62"
}
```

**Genie: analytical question -> inspectable SQL**: `POST /v1/genie/ask` -> HTTP 200 in 18424 ms
```json
{
 "conversation_id": "01f1cd563fe81960a8add63f689961cc",
 "message_id": "01f1cd563ff3162aa76e31762310039b",
 "status": "COMPLETED",
 "answer": "**LATAM** has the lowest lifetime ROI at **1.69**, based on total spend of **$2,472,404**. In this result, **LATAM** is the lowest-performing region on ROI among the regions included in the query.",
 "api_call": null,
 "queries": [
  {
   "sql": "WITH regional_roi AS (\n  SELECT\n    region,\n    ROUND(try_divide(SUM(revenue_usd),SUM(spend_usd)),2) AS roi,\n    ROUND(SUM(spend_usd)) AS spend_usd\n  FROM at_workspace_102126.renewal_radar.gold_regional_seasonality\n  WHERE region IS NOT NULL AND revenue_usd IS NOT NULL AND spend_usd IS NOT NULL AND spend_usd <> 0\n  GROUP BY region\n), ranked_regions AS (\n  SELECT\n    region,\n    roi,\n    spend_usd,\n    RANK() OVER (ORDER BY roi ASC) AS roi_rank\n  FROM regional_roi\n)\nSELECT region, roi, spend_usd\nFROM ranked_regions\nWHERE roi_rank = 1\nORDER BY region",
   "description": "You want to find the region with the lowest return on investment (ROI) based on the total revenue and spend in each region."
  }
 ],
 "genie_url": "https://dbc-37e28a61-cc0c.cloud.databricks.com/genie/rooms/01f1cd55187c1612a46bd87e6dcfd7da/chats/01f1cd563fe81960a8add63f689961cc"
}
```

### Request log (`radar_app.request_log` in Lakebase)

| ts | method | route | status | duration_ms | key_label |
|---|---|---|---|---|---|
| 2026-10-21T13:49:52.734084+00:00 | POST | /v1/genie/ask | 200 | 18079.2 |  |
| 2026-10-21T13:49:34.313476+00:00 | POST | /v1/genie/ask | 200 | 12563.0 |  |
| 2026-10-21T13:49:21.434400+00:00 | POST | /v1/campaigns/explain | 200 | 3045.9 | portfolio operator |
| 2026-10-21T13:49:18.026871+00:00 | GET | /v1/portfolio/actions | 200 | 15.7 |  |
| 2026-10-21T13:49:17.657080+00:00 | GET | /v1/portfolio/summary | 200 | 31.2 |  |
| 2026-10-21T13:49:17.314035+00:00 | GET | /v1/portfolio/summary | 401 | 2.0 |  |
| 2026-10-21T13:49:16.977037+00:00 | GET | /v1/portfolio/summary | 403 | 10.2 |  |
| 2026-10-21T13:49:16.461491+00:00 | GET | /v1/brands/ACC-0001/renewal-health | 404 | 8.4 |  |
| 2026-10-21T13:49:16.106805+00:00 | GET | /v1/brands/ACC-0000/renewal-health | 200 | 16.1 |  |
| 2026-10-21T13:48:08.448514+00:00 | POST | /v1/campaigns/explain | 200 | 3461.5 | portfolio operator |
| 2026-10-21T13:47:35.704178+00:00 | GET | /v1/pipeline/last-run | 200 | 683.1 |  |
| 2026-10-21T13:47:34.653530+00:00 | POST | /v1/campaigns/explain | 200 | 2775.2 | portfolio operator |
