# Raw execution transcript

Captured 2026-10-21T14:50:23+00:00 by `scripts/capture_evidence.py`. Every block below was fetched live at capture time.

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

**health (Lakebase round trip)**: `GET /v1/health` -> HTTP 200 in 345 ms
```json
{
 "status": "ok",
 "brands_served": 120,
 "lakebase_round_trip_ms": 13.4,
 "serving_endpoint": "databricks-claude-haiku-5-5"
}
```

**brand key reads its own brand**: `GET /v1/brands/ACC-0000/renewal-health` -> HTTP 200 in 349 ms
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

**brand key asks for ANOTHER brand -> 404**: `GET /v1/brands/ACC-0001/renewal-health` -> HTTP 404 in 347 ms
```json
{
 "detail": "brand not found"
}
```

**brand key asks for portfolio data -> 403**: `GET /v1/portfolio/summary` -> HTTP 403 in 318 ms
```json
{
 "detail": "portfolio-scoped key required"
}
```

**no key -> 401**: `GET /v1/portfolio/summary` -> HTTP 401 in 310 ms
```json
{
 "detail": "X-Api-Key header is required"
}
```

**portfolio summary (book, renewals, spend, top at-risk)**: `GET /v1/portfolio/summary` -> HTTP 200 in 433 ms
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
 ],
 "book": {
  "brands": 120,
  "arr_usd": 17812200.0,
  "avg_churn": 0.4888241666666667,
  "expected_loss_usd": 8283085.59,
  "renewing_90d": 50,
  "renewing_90d_arr": 6612300.0,
  "high_risk_renewing_90d": 22,
  "high_risk_renewing_90d_arr": 2922800.0
 },
 "spend": {
  "campaigns": 900,
  "active": 48,
  "spend_usd": 28665877.759999983,
  "revenue_usd": 54865087.289999984,
  "roi": 1.9139510657705399,
  "below_breakeven": 34
 },
 "by_region": [
  {
   "region": "APAC",
   "brands": 15,
   "arr_usd": 1598100.0,
   "avg_churn_pct": 47.0,
   "high_risk": 6
  },
  {
   "region": "EMEA",
   "brands": 40,
   "arr_usd": 6188600.0,
   "avg_churn_pct": 55.0,
   "high_risk": 18
  },
  {
   "region": "LATAM",
   "brands": 11,
   "arr_usd": 1437400.0,
   "avg_churn_pct": 59.0,
   "high_risk": 6
  },
  {
   "region": "NA",
   "brands": 54,
   "arr_usd": 8588100.0,
   "avg_churn_pct": 43.0,
   "high_risk": 16
  }
 ],
 "top_at_risk": [
  {
   "account_id": "ACC-0060",
   "brand_name": "Aster Provisions",
   "region": "NA",
   "tier": "enterprise",
   "arr_usd": 558900.0,
   "renewal_date": "2027-04-23",
   "renewal_risk_score": 0.9026,
   "expected_loss_usd": 504463.13999999996
  },
  {
   "account_id": "ACC-0094",
   "brand_name": "Orchard Beauty",
   "region": "NA",
   "tier": "enterprise",
   "arr_usd": 444100.0,
   "renewal_date": "2027-01-03",
   "renewal_risk_score": 0.947,
   "expected_loss_usd": 420562.69999999995
  },
  {
   "account_id": "ACC-0119",
   "brand_name": "Tamarack & Co",
   "region": "LATAM",
   "tier": "enterprise",
   "arr_usd": 377600.0,
   "renewal_date": "2026-11-01",
   "renewal_risk_score": 0.8932,
   "expected_loss_usd": 337272.32
  },
  {
   "account_id": "ACC-0116",
   "brand_name": "Quill Provisions",
   "region": "APAC",
   "tier": "enterprise",
   "arr_usd": 516700.0,
   "renewal_date": "2027-03-27",
   "renewal_risk_score": 0.6072,
   "expected_loss_usd": 313740.24
  },
  {
   "account_id": "ACC-0118",
   "brand_name": "Saffron Beauty",
   "region": "EMEA",
   "tier": "enterprise",
   "
```

**brand overview: the Saffron Beauty view**: `GET /v1/brands/ACC-0118/overview` -> HTTP 200 in 408 ms
```json
{
 "brand": {
  "account_id": "ACC-0118",
  "brand_name": "Saffron Beauty",
  "region": "EMEA",
  "country": "UK",
  "tier": "enterprise",
  "industry": "fashion",
  "arr_usd": 316300.0,
  "renewal_date": "2027-05-04",
  "owner_email": "csm6@traackr-demo.example",
  "avg_roi_180d": 1.2762495618320735,
  "active_campaigns": 6,
  "revenue_trend_90d": 0.6,
  "late_invoice_rate": 0.05555555555555555,
  "renewal_risk_score": 0.8026,
  "risk_band": "high",
  "scored_at": "2026-10-21T13:39:38.241213+00:00",
  "model_uri": "models:/at_workspace_102126.renewal_radar.renewal_risk@champion",
  "days_to_renewal": 195
 },
 "campaigns": {
  "campaigns": 18,
  "active": 1,
  "ended": 17,
  "spend_usd": 531825.6599999999,
  "revenue_usd": 864085.4299999999,
  "roi": 1.6247531756929519,
  "below_breakeven": 3
 },
 "region_roi": 2.005322145580693,
 "risk_peers": {
  "region_churn": 0.553965,
  "tier_churn": 0.35680500000000004,
  "portfolio_churn": 0.4888241666666667
 },
 "roi_rank": {
  "rank": 86,
  "brands": 120
 },
 "best_campaign": {
  "campaign_name": "Saffron Beauty Spring Push 560",
  "roi": 3.229,
  "spend_usd": 31603.06
 },
 "worst_campaign": {
  "campaign_name": "Saffron Beauty Fall Push 697",
  "roi": 0.501,
  "spend_usd": 19414.37
 },
 "actions": {
  "flagged": 3,
  "opportunity_usd": 136100.78,
  "spend_90d_usd": 76187.84
 },
 "genie_questions": 2
}
```

**brand key cannot open another brand's overview -> 404**: `GET /v1/brands/ACC-0094/overview` -> HTTP 404 in 342 ms
```json
{
 "detail": "brand not found"
}
```

**top persisted ai_gen actions**: `GET /v1/portfolio/actions?limit=2` -> HTTP 200 in 473 ms
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

**live foundation-model explanation**: `POST /v1/campaigns/explain` -> HTTP 200 in 3756 ms
```json
{
 "campaign_id": "CMP-00080",
 "endpoint": "databricks-claude-haiku-5-5",
 "explanation": "The Orchard Beauty Fall Push 80 has a 90-day ROI of 0.326, far below the regional benchmark of 1.969, and the brand carries a high modelled renewal risk of 95%. Because of this gap and risk, it needs attention now, so prioritizing retention strategies for Orchard Beauty to mitigate that renewal risk should stay at the top of the action list.",
 "usage": {
  "completion_tokens": 412,
  "prompt_tokens": 124,
  "total_tokens": 536
 },
 "latency_ms": 3370
}
```

**Genie: API question -> script, no SQL**: `POST /v1/genie/ask` -> HTTP 200 in 13331 ms
```json
{
 "conversation_id": "01f1cd5ecc1519709f18b90520921868",
 "message_id": "01f1cd5ecc1f1f53980f1a32c4d87692",
 "status": "COMPLETED",
 "answer": "Two **GET** endpoints show renewal risk:\n- **/v1/brands/{account_id}/renewal-health** \u2014 modelled renewal risk score, band, and the drivers behind it\n- **/v1/portfolio/risk** \u2014 all brands ranked by modelled renewal risk\nBoth use **X-Api-Key** authentication, with the first available for **brand or portfolio** access and the second for **portfolio only**.",
 "api_call": {
  "method": "GET",
  "path": "/v1/brands/{account_id}/renewal-health",
  "purpose": "Modelled churn probability, band and drivers",
  "script": "curl -s -X GET 'https://traackr-renewal-radar-7474647371758861.aws.databricksapps.com/v1/brands/ACC-0000/renewal-health' \\\n  -H 'X-Api-Key: rr_demo_portfolio' -H 'Accept: application/json'"
 },
 "queries": [],
 "genie_url": "https://dbc-37e28a61-cc0c.cloud.databricks.com/genie/rooms/01f1cd55187c1612a46bd87e6dcfd7da/chats/01f1cd5ecc1519709f18b90520921868"
}
```

**Genie asked from a BRAND view (scoped to that brand)**: `POST /v1/genie/ask` -> HTTP 200 in 17364 ms
```json
{
 "conversation_id": "01f1cd5ed3ff1bc3aade214cba8ccff3",
 "message_id": "01f1cd5ed40a1197803e5433017ca98f",
 "status": "COMPLETED",
 "answer": "For **Saffron Beauty** (**account_id ACC-0118**), the renewal risk is **high** with a renewal risk score of **0.8026**. The score was recorded on **2026-10-21 13:39:38 UTC**, and the renewal date is **2027-05-04**.",
 "api_call": null,
 "queries": [
  {
   "sql": "SELECT `brand_name`, `account_id`, `renewal_risk_score`, `risk_band`, `renewal_date`, `scored_at` FROM `at_workspace_102126`.`renewal_radar`.`brand_radar` WHERE `account_id` = 'ACC-0118'",
   "description": "You want to see the renewal risk details for the brand Saffron Beauty with account ID ACC-0118."
  }
 ],
 "genie_url": "https://dbc-37e28a61-cc0c.cloud.databricks.com/genie/rooms/01f1cd55187c1612a46bd87e6dcfd7da/chats/01f1cd5ed3ff1bc3aade214cba8ccff3"
}
```

**that brand's question history (only its own view)**: `GET /v1/genie/history?limit=5` -> HTTP 200 in 624 ms
```json
[
 {
  "ts": "2026-10-21T14:51:16.083380+00:00",
  "view": "Saffron Beauty (ACC-0118)",
  "asked_by": "andrea.tardif@databricks.com",
  "status": 200,
  "duration_ms": 17012,
  "question": "What is our renewal risk?",
  "intent": "analytical",
  "answer": "For **Saffron Beauty** (**account_id ACC-0118**), the renewal risk is **high** with a renewal risk score of **0.8026**. The score was recorded on **2026-10-21 13:39:38 UTC**, and the renewal date is **2027-05-04**.",
  "conversation_id": "01f1cd5ed3ff1bc3aade214cba8ccff3",
  "genie_url": "https://dbc-37e28a61-cc0c.cloud.databricks.com/genie/rooms/01f1cd55187c1612a46bd87e6dcfd7da/chats/01f1cd5ed3ff1bc3aade214cba8ccff3",
  "error": null
 },
 {
  "ts": "2026-10-21T14:49:37.608939+00:00",
  "view": "Saffron Beauty (ACC-0118)",
  "asked_by": "andrea.tardif@databricks.com",
  "status": 200,
  "duration_ms": 25053,
  "question": "Show me the renewal risk for Orchard Beauty",
  "intent": "analytical",
  "answer": "I can\u2019t share renewal risk for Orchard Beauty: within **account_id ACC-0118**, there is **no Orchard Beauty record** in the available data.",
  "conversation_id": "01f1cd5e94831b6d899efccebd970074",
  "genie_url": "https://dbc-37e28a61-cc0c.cloud.databricks.com/genie/rooms/01f1cd55187c1612a46bd87e6dcfd7da/chats/01f1cd5e94831b6d899efccebd970074",
  "error": null
 },
 {
  "ts": "2026-10-21T14:49:12.089779+00:00",
  "view": "Saffron Beauty (ACC-0118)",
  "asked_by": "andrea.tardif@databricks.com",
  "status": 200,
  "duration_ms": 33765,
  "question": "What is our renewal risk and which campaigns are underperforming?",
  "intent": "analytical",
  "answer": "For **Saffron Beauty (ACC-0118)**, the renewal risk is **high** with a score of **0.8026** and a renewal date of **2027-05-04**. The underperforming campaigns shown all have **90-day ROI below the 2.10 benchmark**, and examples include:\n- **Saffron Beauty Fall Push 240** \u2014 ROI **0.63** vs benchmark **2.10**; estimated upside **$69.1K**\n- **Saffron Beauty Fall Push 697** \u2014 ROI **0.50** vs benchmark **2.10**; estimated upside **$37.2K**\n- **Saffron Beauty Fall Push 691** \u2014 ROI **0.68** vs benchmark **2.10**; estimated upside **$29.9K**\nAcross the 3 campaigns shown, ROI ranges from **0.50 to 0.68**, so each is materially below the current performance benchmark.",
  "conversation_id": "01f1cd5e804c14f7910ac3ff4cc71be8",
  "genie_url": "https://dbc-37e28a61-cc0c.cloud.databricks.com/genie/rooms/01f1cd55187c1612a46bd87e6dcfd7da/chats/01f1cd5e804c14f7910ac3ff4cc71be8",
  "error": null
 }
]
```

**another brand's history is empty of those questions**: `GET /v1/genie/history?limit=5` -> HTTP 200 in 366 ms
```json
[]
```

**operator history: all views, with asker and view**: `GET /v1/genie/history?limit=6` -> HTTP 200 in 363 ms
```json
[
 {
  "ts": "2026-10-21T14:51:16.083380+00:00",
  "view": "Saffron Beauty (ACC-0118)",
  "asked_by": "andrea.tardif@databricks.com",
  "status": 200,
  "duration_ms": 17012,
  "question": "What is our renewal risk?",
  "intent": "analytical",
  "answer": "For **Saffron Beauty** (**account_id ACC-0118**), the renewal risk is **high** with a renewal risk score of **0.8026**. The score was recorded on **2026-10-21 13:39:38 UTC**, and the renewal date is **2027-05-04**.",
  "conversation_id": "01f1cd5ed3ff1bc3aade214cba8ccff3",
  "genie_url": "https://dbc-37e28a61-cc0c.cloud.databricks.com/genie/rooms/01f1cd55187c1612a46bd87e6dcfd7da/chats/01f1cd5ed3ff1bc3aade214cba8ccff3",
  "error": null
 },
 {
  "ts": "2026-10-21T14:50:58.709058+00:00",
  "view": "portfolio operator",
  "asked_by": "andrea.tardif@databricks.com",
  "status": 200,
  "duration_ms": 12920,
  "question": "Which API endpoint shows renewal risk?",
  "intent": "api",
  "answer": "Two **GET** endpoints show renewal risk:\n- **/v1/brands/{account_id}/renewal-health** \u2014 modelled renewal risk score, band, and the drivers behind it\n- **/v1/portfolio/risk** \u2014 all brands ranked by modelled renewal risk\nBoth use **X-Api-Key** authentication, with the first available for **brand or portfolio** access and the second for **portfolio only**.",
  "conversation_id": "01f1cd5ecc1519709f18b90520921868",
  "genie_url": "https://dbc-37e28a61-cc0c.cloud.databricks.com/genie/rooms/01f1cd55187c1612a46bd87e6dcfd7da/chats/01f1cd5ecc1519709f18b90520921868",
  "error": null
 },
 {
  "ts": "2026-10-21T14:50:03.076676+00:00",
  "view": "portfolio operator",
  "asked_by": "andrea.tardif@databricks.com",
  "status": 200,
  "duration_ms": 25073,
  "question": "How many brands are high risk?",
  "intent": "analytical",
  "answer": "There are **46** brands with `risk_band` marked as **high**. Based on the result shown, the high-risk brand count is **46**.",
  "conversation_id": "01f1cd5ea3ae149c9fa2f2ef381bf765",
  "genie_url": "https://dbc-37e28a61-cc0c.cloud.databricks.com/genie/rooms/01f1cd55187c1612a46bd87e6dcfd7da/chats/01f1cd5ea3ae149c9fa2f2ef381bf765",
  "error": null
 },
 {
  "ts": "2026-10-21T14:49:37.608939+00:00",
  "view": "Saffron Beauty (ACC-0118)",
  "asked_by": "andrea.tardif@databricks.com",
  "status": 200,
  "duration_ms": 25053,
  "question": "Show me the renewal risk for Orchard Beauty",
  "intent": "analytical",
  "answer": "I can\u2019t share renewal risk for Orchard Beauty: within **account_id ACC-0118**, there is **no Orchard Beauty record** in the available data.",
  "conversation_id": "0
```

**Genie: analytical question -> inspectable SQL**: `POST /v1/genie/ask` -> HTTP 200 in 18179 ms
```json
{
 "conversation_id": "01f1cd5edf3e1fb08bd80de383ee739f",
 "message_id": "01f1cd5edf471277ab342a757e93ca97",
 "status": "COMPLETED",
 "answer": "The region with the **lowest ROI** is **LATAM**, with an ROI of **1.69** on **$2,472,404** in spend. In this result set, **LATAM** is the lowest-performing region by ROI.",
 "api_call": null,
 "queries": [
  {
   "sql": "WITH `regional_roi` AS (\n  SELECT\n    `region`,\n    try_divide(SUM(`revenue_usd`),SUM(`spend_usd`)) AS `roi`,\n    SUM(`spend_usd`) AS `spend_usd`\n  FROM `at_workspace_102126`.`renewal_radar`.`gold_regional_seasonality`\n  WHERE `region` IS NOT NULL\n  GROUP BY `region`\n), `ranked_regions` AS (\n  SELECT\n    `region`,\n    ROUND(`roi`, 2) AS `roi`,\n    ROUND(`spend_usd`) AS `spend_usd`,\n    RANK() OVER (ORDER BY `roi` ASC) AS `roi_rank`\n  FROM `regional_roi`\n)\nSELECT `region`, `roi`, `spend_usd`\nFROM `ranked_regions`\nWHERE `roi_rank` <= 1\nORDER BY `roi` ASC, `region` ASC",
   "description": "You want to find the region with the lowest return on investment (ROI) based on lifetime data."
  }
 ],
 "genie_url": "https://dbc-37e28a61-cc0c.cloud.databricks.com/genie/rooms/01f1cd55187c1612a46bd87e6dcfd7da/chats/01f1cd5edf3e1fb08bd80de383ee739f"
}
```

### Request log (`radar_app.request_log` in Lakebase)

| ts | method | route | status | duration_ms | key_label |
|---|---|---|---|---|---|
| 2026-10-21T14:51:35.607753+00:00 | POST | /v1/genie/ask | 200 | 17824.0 | portfolio operator |
| 2026-10-21T14:51:17.440010+00:00 | GET | /v1/genie/history | 200 | 22.1 | portfolio operator |
| 2026-10-21T14:51:17.074941+00:00 | GET | /v1/genie/history | 200 | 18.4 | Orchard Beauty (ACC-0094) |
| 2026-10-21T14:51:16.709739+00:00 | GET | /v1/genie/history | 200 | 18.8 | Saffron Beauty (ACC-0118) |
| 2026-10-21T14:51:16.083380+00:00 | POST | /v1/genie/ask | 200 | 17011.6 | Saffron Beauty (ACC-0118) |
| 2026-10-21T14:50:58.709058+00:00 | POST | /v1/genie/ask | 200 | 12919.6 | portfolio operator |
| 2026-10-21T14:50:45.386354+00:00 | POST | /v1/campaigns/explain | 200 | 3370.3 | portfolio operator |
| 2026-10-21T14:50:41.632786+00:00 | GET | /v1/portfolio/actions | 200 | 134.1 | portfolio operator |
| 2026-10-21T14:50:41.163801+00:00 | GET | /v1/brands/ACC-0094/overview | 404 | 12.0 | Saffron Beauty (ACC-0118) |
| 2026-10-21T14:50:40.816083+00:00 | GET | /v1/brands/ACC-0118/overview | 200 | 100.3 | Saffron Beauty (ACC-0118) |
| 2026-10-21T14:50:40.406788+00:00 | GET | /v1/portfolio/summary | 200 | 93.0 | portfolio operator |
| 2026-10-21T14:50:39.976021+00:00 | GET | /v1/portfolio/summary | 401 | 1.0 |  |
