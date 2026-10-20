-- Gold layer — analytics-ready aggregates as materialized views

-- Per-creator-day performance
CREATE OR REFRESH MATERIALIZED VIEW gold_creator_performance_daily
COMMENT "Gold: daily creator performance"
AS
SELECT
  e.creator_id, e.date, e.tier, e.platform, e.handle,
  SUM(e.impressions) AS impressions,
  SUM(e.engagements) AS engagements,
  SUM(e.video_views) AS video_views,
  COALESCE(SUM(rev.attributed_revenue_usd), 0) AS attributed_revenue_usd,
  COALESCE(SUM(spend.ad_spend_usd), 0) AS ad_spend_usd,
  CASE
    WHEN COALESCE(SUM(spend.ad_spend_usd), 0) > 0
    THEN COALESCE(SUM(rev.attributed_revenue_usd), 0) / SUM(spend.ad_spend_usd)
    ELSE 0
  END AS roi
FROM silver_engagement e
LEFT JOIN (
  SELECT creator_id, transaction_date AS date, SUM(amount_usd) AS attributed_revenue_usd
  FROM silver_revenue
  WHERE kind = 'creator_attribution' AND status = 'paid'
  GROUP BY creator_id, transaction_date
) rev ON e.creator_id = rev.creator_id AND e.date = rev.date
LEFT JOIN (
  -- ad spend at creator-day grain — attribute by campaigns this creator was attributed to
  SELECT r.creator_id, s.date, SUM(s.spend_usd) / NULLIF(c.creator_count, 0) AS ad_spend_usd
  FROM silver_ad_spend s
  JOIN silver_revenue r ON r.campaign_id = s.campaign_id AND r.transaction_date = s.date
  JOIN (
    SELECT campaign_id, COUNT(DISTINCT creator_id) AS creator_count
    FROM silver_revenue WHERE kind='creator_attribution' GROUP BY campaign_id
  ) c ON c.campaign_id = s.campaign_id
  WHERE r.kind = 'creator_attribution'
  GROUP BY r.creator_id, s.date, c.creator_count
) spend ON e.creator_id = spend.creator_id AND e.date = spend.date
GROUP BY e.creator_id, e.date, e.tier, e.platform, e.handle;

-- Per-campaign ROI
CREATE OR REFRESH MATERIALIZED VIEW gold_campaign_roi
COMMENT "Gold: per-campaign ROI"
AS
SELECT
  c.campaign_id, c.account_id, c.brand_name, c.name, c.status, c.start_date, c.end_date, c.budget_usd,
  COALESCE(SUM(s.spend_usd), 0) AS total_spend_usd,
  COALESCE(SUM(CASE WHEN r.kind='creator_attribution' AND r.status='paid' THEN r.amount_usd END), 0) AS total_revenue_usd,
  CASE
    WHEN COALESCE(SUM(s.spend_usd), 0) > 0
    THEN COALESCE(SUM(CASE WHEN r.kind='creator_attribution' AND r.status='paid' THEN r.amount_usd END), 0) / SUM(s.spend_usd)
    ELSE 0
  END AS roi,
  GREATEST(MAX(s.date), MAX(r.transaction_date)) AS last_activity_date
FROM silver_campaigns c
LEFT JOIN silver_ad_spend s ON s.campaign_id = c.campaign_id
LEFT JOIN silver_revenue r ON r.campaign_id = c.campaign_id
GROUP BY c.campaign_id, c.account_id, c.brand_name, c.name, c.status, c.start_date, c.end_date, c.budget_usd;

-- Per-brand renewal health
CREATE OR REFRESH MATERIALIZED VIEW gold_brand_renewal_health
COMMENT "Gold: brand renewal health with derived health score"
AS
WITH camp AS (
  SELECT account_id,
         COUNT(*) FILTER (WHERE status = 'active') AS active_campaigns,
         COUNT(*) AS total_campaigns,
         AVG(roi) AS avg_campaign_roi,
         MAX(last_activity_date) AS last_activity_date
  FROM gold_campaign_roi
  GROUP BY account_id
), rev AS (
  SELECT
    COALESCE(revenue_account_id, campaign_account_id) AS account_id,
    SUM(amount_usd) FILTER (WHERE status='paid') AS ytd_attributed_revenue_usd
  FROM silver_revenue
  WHERE transaction_date >= date_sub(current_date(), 365)
    AND (kind = 'creator_attribution' OR kind = 'brand_invoice')
  GROUP BY COALESCE(revenue_account_id, campaign_account_id)
)
SELECT
  b.account_id, b.brand_name, b.tier, b.country, b.renewal_status, b.renewal_date,
  b.renewal_arr_usd,
  COALESCE(rev.ytd_attributed_revenue_usd, 0) AS ytd_attributed_revenue_usd,
  COALESCE(camp.active_campaigns, 0) AS active_campaigns,
  COALESCE(camp.last_activity_date, b.renewal_date) AS last_activity_date,
  CAST(LEAST(100,
    COALESCE(camp.active_campaigns, 0) * 8
    + COALESCE(camp.avg_campaign_roi, 0) * 15
    + CASE WHEN COALESCE(camp.last_activity_date, current_date() - 999) >= date_sub(current_date(), 30) THEN 30 ELSE 5 END
    + CASE WHEN b.renewal_status = 'renewed' THEN 20 ELSE 10 END
  ) AS INT) AS renewal_health_score
FROM silver_brands b
LEFT JOIN camp ON camp.account_id = b.account_id
LEFT JOIN rev ON rev.account_id = b.account_id;
