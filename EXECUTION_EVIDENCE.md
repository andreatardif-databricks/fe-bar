# Readable Execution Evidence

This file contains actual text output captured from the deployed build. It is not expected output or a screenshot.

## 1. Integrated orchestration run

Workspace job: `[prod] Pulsar — Daily Orchestration` (`357780382169889`)

Parent run `969307369960771`: `TERMINATED / SUCCESS`

```text
generate_demo_data       run 893211176158689   107 s   SUCCESS
run_pipeline             run 80910690997596    202 s   SUCCESS
generate_ai_insights     run 1007858851997711  305 s   SUCCESS
trigger_lakebase_sync    run 822297336579864     57 s   SUCCESS
freshness_check          run 93846752616110      23 s   SUCCESS
```

Dependency chain executed by `databricks.yml`:

```text
generate_demo_data → run_pipeline → generate_ai_insights → trigger_lakebase_sync → freshness_check
```

## 2. Actual `ai_gen` output

Implementation: `AI_GEN_RECOMMENDATIONS.sql` and `src/jobs/generate_ai_insights.py`

Persisted table: `at_10526_workspace.influencer_engagement_fe_bar.ai_campaign_insights`

Generation timestamp: `2026-10-19T20:39:30.918Z`

```json
{
  "brand_name": "Coach",
  "campaign_id": "CMP-01337",
  "campaign_name": "Coach Spring Capsule",
  "roi": "0.273",
  "model_function": "ai_gen",
  "recommendation": "Based on the campaign metrics, one concise action for a marketing leader is to re-evaluate and potentially reduce the USD 9.05 billion spend on the Coach Spring Capsule campaign, as the current ROI of 0.273 indicates that the campaign is generating approximately $0.27 in revenue for every dollar spent."
}
```

## 3. Actual model-serving endpoint call

Endpoint: `databricks-claude-haiku-5-5`  
Underlying model returned by the endpoint: `us.anthropic.claude-haiku-5-5`  
Implementation: `MODEL_ENDPOINT_RECOMMENDATION.py`

Input:

```json
{"campaign":"Holiday Glow","spend_usd":125000,"attributed_revenue_usd":187500,"roi":1.5}
```

Captured response from deployed `POST /v1/model-recommendation`:

```json
{
  "endpoint": "databricks-claude-haiku-5-5",
  "recommendation": "Recommended action: Reallocate a portion of the remaining Holiday Glow budget toward the creators and content formats driving the highest return, and pause spend on the lowest performers, since the campaign currently returns 1.5x ROI (USD 187,500 revenue on USD 125,000 spend).",
  "usage": {"completion_tokens":98,"prompt_tokens":114,"total_tokens":212}
}
```

## 4. Lakebase synchronization

```json
{"name":"at_10526_workspace.influencer_engagement_fe_bar.synced_creators","pipeline_id":"77b1d73b-9668-49d4-bd33-29a52e9de4d6","state":"SYNCED_TABLE_ONLINE_NO_PENDING_UPDATE"}
{"name":"at_10526_workspace.influencer_engagement_fe_bar.synced_campaigns","pipeline_id":"195d467e-82c9-4aba-b832-4d7f5b97ea45","state":"SYNCED_TABLE_ONLINE_NO_PENDING_UPDATE"}
```

## 5. Deployed application responses

```json
{"status":"ok"}
{"source":"lakebase","brands":200,"campaigns":2000,"creators":5000}
{"ai_insight_count":8,"source":"at_10526_workspace.influencer_engagement_fe_bar.ai_campaign_insights"}
```

## 6. Raw event to customer-facing API

Synthetic change: campaign `CMP-01337`, status `active` → `paused`.

```json
{
  "complete": true,
  "stages": [
    {"key":"raw","at":"2026-10-20T15:28:15.693680+00:00"},
    {"key":"bronze","at":"2026-10-20T15:31:32.710342+00:00"},
    {"key":"platinum","at":"2026-10-20T15:31:34.998700+00:00"},
    {"key":"lakebase","at":"2026-10-20T15:32:37.743914+00:00"},
    {"key":"api","at":"2026-10-20T15:32:37.785456+00:00"}
  ],
  "per_stage_ms":{"bronze":197016,"platinum":2288,"lakebase":62745,"api":41},
  "total_ms":262091,
  "error":null
}
```

Measured total latency: **262.091 seconds (4 minutes 22.091 seconds)**.
