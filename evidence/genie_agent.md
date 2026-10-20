# Genie Agent Execution Evidence

Agent: `Traackr Influencer Revenue Agent`  
Space ID: `01f1cbfef7e81a1d8d9161f8fd8d65f6`

## Business question

Question: `Which campaigns have the highest ROI?`

Conversation: `01f1cc01f64619d580feedb42800ce39`

Generated SQL:

```sql
SELECT campaign_id, brand_name, name, ROUND(roi, 2) AS roi,
       ROUND(total_revenue_usd, 2) AS revenue_usd
FROM at_10526_workspace.influencer_engagement_fe_bar.gold_campaign_roi
WHERE total_spend_usd > 0 AND roi IS NOT NULL
ORDER BY roi DESC
LIMIT 10
```

Result metadata: `10 rows`

Answer excerpt:

> Based on the gold_campaign_roi source table, the top-performing campaign by ROI is "Mint Drop Burst" from Aurora House, achieving a 25.32x ROI and generating $435.8M in revenue.

## API question through the embedded App route

Question: `Which API endpoint shows renewal risk?`

Conversation: `01f1cc929e631779957b5e1bcc4c3964`

Generated SQL:

```sql
SELECT method, path, purpose, authentication
FROM at_10526_workspace.influencer_engagement_fe_bar.api_endpoint_catalog
WHERE purpose IS NOT NULL AND purpose ILIKE '%renewal%'
```

Answer:

> The API endpoint that shows renewal risk is GET /v1/brands/{brand_id}/renewal-health. It returns renewal health, ARR, revenue, and active campaign KPIs and requires X-Brand-API-Key authentication.

The App response also returned: `AI-generated — verify against the generated SQL and governed source tables.` Execution identity was the signed-in user via OBO.
