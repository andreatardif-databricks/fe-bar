# Persisted GenAI Execution Evidence

Function: Databricks SQL `ai_gen`  
Persisted table: `at_10526_workspace.influencer_engagement_fe_bar.ai_campaign_insights`  
Generation time: `2026-10-19T20:39:30.918Z`

Real output rows:

```json
[
  {
    "brand_name":"Coach",
    "campaign_id":"CMP-01337",
    "campaign_name":"Coach Spring Capsule",
    "roi":"0.273",
    "model_function":"ai_gen",
    "recommendation":"Based on the campaign metrics, one concise action for a marketing leader is to re-evaluate and potentially reduce the USD 9.05 billion spend on the Coach Spring Capsule campaign, as the current ROI of 0.273 indicates that the campaign is generating approximately $0.27 in revenue for every dollar spent."
  },
  {
    "brand_name":"Solstice Works",
    "campaign_id":"CMP-01105",
    "campaign_name":"Gold Rush Rise",
    "roi":"0.373",
    "model_function":"ai_gen",
    "recommendation":"Reduce spend on the Gold Rush Rise campaign, as the current ROI of 0.373 indicates that for every dollar spent, the campaign is only generating approximately 37 cents in attributed revenue."
  }
]
```

The prompt restricts the model to governed campaign name, spend, attributed revenue, and ROI. Results are generated once per orchestration and persisted rather than recomputed on every app request.
