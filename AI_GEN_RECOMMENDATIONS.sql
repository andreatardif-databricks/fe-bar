-- Executed by src/jobs/generate_ai_insights.py after the governed Lakeflow pipeline succeeds.
-- The output is persisted, synchronized to Lakebase, and served by /v1/ai-insights.
CREATE OR REPLACE TABLE at_10526_workspace.influencer_engagement_fe_bar.ai_campaign_insights
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
FROM at_10526_workspace.influencer_engagement_fe_bar.gold_campaign_roi
WHERE total_spend_usd > 0
ORDER BY total_revenue_usd DESC
LIMIT 8;

SELECT campaign_id, roi, recommendation, generated_at
FROM at_10526_workspace.influencer_engagement_fe_bar.ai_campaign_insights
ORDER BY total_revenue_usd DESC
LIMIT 3;
