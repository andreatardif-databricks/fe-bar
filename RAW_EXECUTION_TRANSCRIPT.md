# Raw Execution Transcript

Captured directly from Databricks CLI and the deployed application on 2026-10-20. JSON formatting is compacted only; identifiers, states, timings, model output, and persisted observability values are unchanged.

## Deployed Foundation Model Response

```json
{"endpoint":"databricks-claude-haiku-5-5","recommendation":"Recommended action: Reallocate a portion of the remaining Holiday Glow budget toward the highest-performing creators and content formats, and pause spend on underperformers, to push ROI above the current 1.500 (attributed revenue of USD 187,500 on USD 125,000 spend).","usage":{"completion_tokens":95,"prompt_tokens":114,"total_tokens":209}}
```

## Full Orchestration Job

```json
{
  "run_id": 1013848902778635,
  "run_name": "[prod] Pulsar — Daily Orchestration",
  "run_page_url": "https://dbc-01f27b97-0e2e.cloud.databricks.com/?o=7474653524978634#job/357780382169889/run/1013848902778635",
  "start_time": 1792529942019,
  "end_time": 1792530876352,
  "state": {"life_cycle_state":"TERMINATED","result_state":"SUCCESS","state_message":"","user_cancelled_or_timedout":false},
  "tasks": [
    {"task_key":"trigger_lakebase_sync","run_id":666362978599442,"execution_duration":60000,"state":{"life_cycle_state":"TERMINATED","result_state":"SUCCESS"}},
    {"task_key":"freshness_check","run_id":1083316193002497,"execution_duration":29000,"state":{"life_cycle_state":"TERMINATED","result_state":"SUCCESS"}},
    {"task_key":"run_pipeline","run_id":186704072988909,"execution_duration":333000,"state":{"life_cycle_state":"TERMINATED","result_state":"SUCCESS"}},
    {"task_key":"generate_demo_data","run_id":893782176633713,"execution_duration":107000,"state":{"life_cycle_state":"TERMINATED","result_state":"SUCCESS"}},
    {"task_key":"generate_ai_insights","run_id":552228321519043,"execution_duration":391000,"state":{"life_cycle_state":"TERMINATED","result_state":"SUCCESS"}}
  ]
}
```

```text
2026-10-20 17:14:46 "[prod] Pulsar — Daily Orchestration" TERMINATED SUCCESS
```

## MLflow Tables Created in Unity Catalog

```json
[
  {"table_name":"app_otel_logs","table_type":"MANAGED"},
  {"table_name":"traackr_mlflow_otel_annotations","table_type":"MANAGED"},
  {"table_name":"traackr_mlflow_otel_logs","table_type":"MANAGED"},
  {"table_name":"traackr_mlflow_otel_metrics","table_type":"MANAGED"},
  {"table_name":"traackr_mlflow_otel_spans","table_type":"MANAGED"},
  {"table_name":"traackr_mlflow_trace_metadata","table_type":"VIEW"},
  {"table_name":"traackr_mlflow_trace_unified","table_type":"VIEW"}
]
```

## Persisted MLflow Model Trace

```json
{
  "trace_id":"eb239ca2ecc1292110b10c0bca804db6",
  "trace_name":"campaign_model_recommendation",
  "source":"/app/python/source_code/.venv/bin/uvicorn",
  "trace_inputs":{"body":{"campaign_name":"Holiday Glow","spend_usd":125000.0,"attributed_revenue_usd":187500.0,"roi":1.5}},
  "trace_outputs":{"endpoint":"databricks-claude-haiku-5-5","recommendation":"Recommended action: Reallocate a portion of the remaining Holiday Glow budget toward the highest-performing creators and content formats, and pause spend on underperformers, to push ROI above the current 1.500.","usage":{"completion_tokens":95,"prompt_tokens":114,"total_tokens":209}},
  "span_type":"CHAT_MODEL",
  "status_code":"STATUS_CODE_OK"
}
```

The record above is persisted in `at_10526_workspace.influencer_engagement_fe_bar.traackr_mlflow_otel_spans`; its trace metadata view is `traackr_mlflow_trace_metadata`.

## Persisted App OTEL Log

```json
[
  {
    "attributes":"{\"campaign.name\":\"Holiday Glow\",\"campaign.roi\":\"1.5\",\"gen_ai.request.model\":\"databricks-claude-haiku-5-5\",\"gen_ai.system\":\"databricks\"}",
    "body":"Foundation model campaign recommendation completed",
    "duration_ms":"2794.389286002115",
    "event_timestamp":"2026-10-20T20:58:44.965Z",
    "http_method":"POST",
    "http_status_code":"200",
    "route":"/v1/model-recommendation",
    "service_name":"influencer-fe-bar",
    "severity_text":"INFO",
    "span_id":"e943560831e54095",
    "trace_id":"cc04bd6d16f54a9fb49e5491c06d5bfd"
  }
]
```

The OTEL record is persisted in `at_10526_workspace.influencer_engagement_fe_bar.app_otel_logs`. Evidence queries used warehouse `70662a24f8050a48`.
