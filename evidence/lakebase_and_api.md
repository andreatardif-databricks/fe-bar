# Lakebase, App, and Live Propagation Evidence

App URL: `https://influencer-fe-bar-7474653524978634.aws.databricksapps.com`

## Lakebase sync

```json
{"name":"at_10526_workspace.influencer_engagement_fe_bar.synced_creators","pipeline_id":"77b1d73b-9668-49d4-bd33-29a52e9de4d6","state":"SYNCED_TABLE_ONLINE_NO_PENDING_UPDATE"}
{"name":"at_10526_workspace.influencer_engagement_fe_bar.synced_campaigns","pipeline_id":"195d467e-82c9-4aba-b832-4d7f5b97ea45","state":"SYNCED_TABLE_ONLINE_NO_PENDING_UPDATE"}
```

## App smoke tests

```json
{"status":"ok"}
{"synthetic_brand_count":137,"sample":{"brand_name":"Adidas","account_id":"ACC-00003"}}
{"ai_insight_count":8,"source":"at_10526_workspace.influencer_engagement_fe_bar.ai_campaign_insights"}
```

## Real synthetic change event

Input event:

```json
{
  "change_id":"b183508b3c4141e5a0055a70651c3bde",
  "event_id":"EV-CMP-00002002",
  "entity":"campaign",
  "entity_id":"CMP-01337",
  "field":"status",
  "old_value":"active",
  "new_value":"paused",
  "volume_path":"/Volumes/at_10526_workspace/influencer_engagement_fe_bar/cdc_events/campaigns/change_b183508b3c4141e5a0055a70651c3bde.parquet",
  "run_id":"fe35a40e-ecc9-4e93-bc5d-0862497a5059",
  "trigger_error":null
}
```

Completed stage evidence:

```json
{
  "complete":true,
  "stages":[
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

Total click-to-API latency was **262.091 seconds (4 minutes 22.091 seconds)**, within the five-minute demo SLA.
