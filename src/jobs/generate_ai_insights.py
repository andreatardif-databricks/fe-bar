# Databricks notebook source
"""Persist governed GenAI campaign recommendations and API documentation."""
import time
from databricks.sdk import WorkspaceClient

CATALOG = "at_10526_workspace"
SCHEMA = "influencer_engagement_fe_bar"
WAREHOUSE_ID = "70662a24f8050a48"

workspace = WorkspaceClient()


def run(statement: str, label: str) -> None:
    print(f"Running {label}...")
    response = workspace.statement_execution.execute_statement(
        warehouse_id=WAREHOUSE_ID,
        statement=statement,
        wait_timeout="50s",
    )
    while response.status.state.value in ("PENDING", "RUNNING"):
        time.sleep(2)
        response = workspace.statement_execution.get_statement(response.statement_id)
    if response.status.state.value != "SUCCEEDED":
        raise RuntimeError(f"{label} failed: {response.status.error}")
    print(f"  OK: {response.statement_id}")


run(
    f"""
    CREATE OR REPLACE TABLE {CATALOG}.{SCHEMA}.api_endpoint_catalog
    COMMENT 'Governed API reference used by the Traackr Genie Agent'
    AS SELECT * FROM VALUES
      ('GET', '/v1/brands/{{brand_id}}/renewal-health', 'Returns renewal health, ARR, revenue, and active campaign KPIs.', 'X-Brand-API-Key', 'Which endpoint shows renewal risk?'),
      ('GET', '/v1/brands/{{brand_id}}/campaigns', 'Lists a brand campaigns and budget status.', 'X-Brand-API-Key', 'How do I list active campaigns?'),
      ('GET', '/v1/brands/{{brand_id}}/creators', 'Lists the creators available to a brand.', 'X-Brand-API-Key', 'How do I retrieve creator performance?'),
      ('GET', '/v1/ai-insights', 'Returns persisted GenAI campaign recommendations.', 'Databricks user session', 'Which endpoint returns AI recommendations?'),
      ('POST', '/v1/admin/propagation/changes', 'Creates a synthetic raw event and starts the end-to-end propagation demo.', 'Databricks user session', 'How do I run the live event demo?')
    AS endpoints(method, path, purpose, authentication, example_question)
    """,
    "API endpoint catalog",
)

run(
    f"""
    CREATE OR REPLACE TABLE {CATALOG}.{SCHEMA}.ai_campaign_insights
    COMMENT 'Persisted GenAI recommendations generated from governed campaign ROI metrics'
    AS
    SELECT
      campaign_id,
      account_id,
      brand_name,
      name AS campaign_name,
      ROUND(total_spend_usd, 2) AS total_spend_usd,
      ROUND(total_revenue_usd, 2) AS total_revenue_usd,
      ROUND(roi, 3) AS roi,
      ai_gen(concat(
        'You are an influencer marketing performance analyst. Give one concise, specific action ',
        'for a marketing leader based only on these campaign metrics. Do not invent facts. ',
        'Campaign: ', name, '; brand: ', brand_name,
        '; spend USD: ', cast(round(total_spend_usd, 2) as string),
        '; attributed revenue USD: ', cast(round(total_revenue_usd, 2) as string),
        '; ROI: ', cast(round(roi, 3) as string), '.'
      )) AS recommendation,
      current_timestamp() AS generated_at,
      'ai_gen' AS model_function
    FROM {CATALOG}.{SCHEMA}.gold_campaign_roi
    WHERE total_spend_usd > 0
    ORDER BY total_revenue_usd DESC
    LIMIT 8
    """,
    "campaign GenAI insights",
)

print("GenAI output sample:")
sample = workspace.statement_execution.execute_statement(
    warehouse_id=WAREHOUSE_ID,
    statement=f"SELECT campaign_id, roi, recommendation, generated_at FROM {CATALOG}.{SCHEMA}.ai_campaign_insights ORDER BY total_revenue_usd DESC LIMIT 3",
    wait_timeout="30s",
)
for row in sample.result.data_array or []:
    print(row)
