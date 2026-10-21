-- Gold: business metrics. Every number the app, Genie and the deck quote is defined here once.

CREATE OR REFRESH MATERIALIZED VIEW gold_campaign_performance
COMMENT 'Lifetime and trailing-90-day spend, revenue and ROI per campaign'
AS
SELECT
  c.campaign_id, c.account_id, a.brand_name, a.industry, c.region, c.name AS campaign_name, c.status,
  SUM(d.spend_usd) AS spend_usd,
  SUM(d.revenue_usd) AS revenue_usd,
  SUM(d.revenue_usd) / NULLIF(SUM(d.spend_usd), 0) AS roi,
  SUM(CASE WHEN d.day >= date_sub(current_date(), 90) THEN d.spend_usd ELSE 0 END) AS spend_90d_usd,
  SUM(CASE WHEN d.day >= date_sub(current_date(), 90) THEN d.revenue_usd ELSE 0 END) AS revenue_90d_usd,
  SUM(CASE WHEN d.day >= date_sub(current_date(), 90) THEN d.revenue_usd ELSE 0 END)
    / NULLIF(SUM(CASE WHEN d.day >= date_sub(current_date(), 90) THEN d.spend_usd ELSE 0 END), 0) AS roi_90d,
  SUM(d.engagements) / NULLIF(SUM(d.impressions), 0) AS engagement_rate,
  MAX(d.day) AS last_activity_date
FROM silver_campaigns c
JOIN silver_accounts a USING (account_id)
JOIN silver_campaign_day d USING (campaign_id)
GROUP BY c.campaign_id, c.account_id, a.brand_name, a.industry, c.region, c.name, c.status;

-- Seasonality by region: spend and revenue rise at different rates, so ROI itself is seasonal.
CREATE OR REFRESH MATERIALIZED VIEW gold_regional_seasonality
COMMENT 'Monthly spend, revenue and ROI by region'
AS
SELECT region, date_trunc('month', day) AS month,
       SUM(spend_usd) AS spend_usd, SUM(revenue_usd) AS revenue_usd,
       SUM(revenue_usd) / NULLIF(SUM(spend_usd), 0) AS roi
FROM silver_campaign_day
GROUP BY region, date_trunc('month', day);

-- One feature row per brand; column names and definitions mirror the model's training table.
CREATE OR REFRESH MATERIALIZED VIEW gold_brand_features
COMMENT 'Current renewal-risk features per brand'
AS
WITH camp AS (
  SELECT account_id,
         COUNT_IF(last_activity_date >= date_sub(current_date(), 90)) AS active_campaigns,
         SUM(revenue_90d_usd) / NULLIF(SUM(spend_90d_usd), 0) AS avg_roi_180d
  FROM gold_campaign_performance GROUP BY account_id
), trend AS (
  SELECT account_id,
         SUM(CASE WHEN day >= date_sub(current_date(), 90) THEN revenue_usd ELSE 0 END) AS last_90,
         SUM(CASE WHEN day < date_sub(current_date(), 90) AND day >= date_sub(current_date(), 180) THEN revenue_usd ELSE 0 END) AS prev_90
  FROM silver_campaign_day GROUP BY account_id
), inv AS (
  SELECT account_id, AVG(CAST(is_late AS DOUBLE)) AS late_invoice_rate FROM silver_invoices GROUP BY account_id
)
SELECT a.account_id, a.brand_name, a.region, a.country, a.tier, a.industry, a.arr_usd, a.renewal_date, a.owner_email,
       COALESCE(camp.avg_roi_180d, 0) AS avg_roi_180d,
       COALESCE(camp.active_campaigns, 0) AS active_campaigns,
       GREATEST(-0.5, LEAST(0.6, COALESCE((trend.last_90 - trend.prev_90) / NULLIF(trend.prev_90, 0), 0))) AS revenue_trend_90d,
       COALESCE(inv.late_invoice_rate, 0) AS late_invoice_rate
FROM silver_accounts a
LEFT JOIN camp USING (account_id)
LEFT JOIN trend USING (account_id)
LEFT JOIN inv USING (account_id);

-- Bottom-up reallocation opportunity.
-- An underperformer is an active-in-90-days campaign with ROI below 1.0 and material spend.
-- Shifting 30% of its trailing-90-day spend (annualised x4) to the regional benchmark earns
-- the ROI gap on the moved dollars. The benchmark is the median ROI of paying campaigns
-- (roi_90d >= 1.0) in the same region, so the figure is defensible and traceable to rows.
CREATE OR REFRESH MATERIALIZED VIEW gold_reallocation_opportunity
COMMENT 'Underperforming campaigns and the annualised revenue from moving 30% of their spend to the regional benchmark'
AS
WITH benchmark AS (
  SELECT region, PERCENTILE(roi_90d, 0.5) AS benchmark_roi
  FROM gold_campaign_performance WHERE roi_90d >= 1.0 AND spend_90d_usd > 1000
  GROUP BY region
)
SELECT p.campaign_id, p.account_id, p.brand_name, p.region, p.campaign_name,
       p.spend_90d_usd, p.revenue_90d_usd, p.roi_90d, b.benchmark_roi,
       0.30 AS shift_share,
       p.spend_90d_usd * 4 * 0.30 AS annual_spend_shifted_usd,
       p.spend_90d_usd * 4 * 0.30 * (b.benchmark_roi - p.roi_90d) AS incremental_revenue_usd
FROM gold_campaign_performance p
JOIN benchmark b USING (region)
WHERE p.roi_90d < 1.0 AND p.spend_90d_usd > 5000 AND p.last_activity_date >= date_sub(current_date(), 90);
