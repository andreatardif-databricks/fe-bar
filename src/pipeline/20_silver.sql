-- Silver: conformed entities. One current row per business key, quality filters applied.

CREATE OR REFRESH MATERIALIZED VIEW silver_accounts
COMMENT 'Current brand accounts (latest ingested row wins)'
AS
SELECT account_id, brand_name, industry, region, country, tier, arr_usd, renewal_date, owner_email
FROM (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY account_id ORDER BY _ingested_at DESC) AS rn
  FROM bronze_accounts
)
WHERE rn = 1;

CREATE OR REFRESH MATERIALIZED VIEW silver_campaigns
COMMENT 'Current campaign definitions resolved from the ordered change feed'
AS
SELECT campaign_id, account_id, name, region, start_date, end_date, budget_usd, status
FROM (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY campaign_id ORDER BY seq DESC) AS rn
  FROM bronze_campaign_cdc
)
WHERE rn = 1 AND op <> 'DELETE';

-- Daily campaign grain: spend, attributed revenue and engagement side by side.
-- Refunded sales are excluded from revenue; the refund count is kept for monitoring.
CREATE OR REFRESH MATERIALIZED VIEW silver_campaign_day
COMMENT 'Daily spend, paid revenue and engagement per campaign'
AS
WITH spend AS (
  SELECT campaign_id, spend_date AS day, SUM(spend_usd) AS spend_usd, SUM(clicks) AS clicks
  FROM bronze_ad_spend GROUP BY campaign_id, spend_date
), revenue AS (
  SELECT campaign_id, sale_date AS day,
         SUM(CASE WHEN payment_status = 'paid' THEN revenue_usd ELSE 0 END) AS revenue_usd,
         SUM(CASE WHEN payment_status = 'refunded' THEN 1 ELSE 0 END) AS refunded_sales
  FROM bronze_creator_sales GROUP BY campaign_id, sale_date
), social AS (
  SELECT campaign_id, event_date AS day, SUM(impressions) AS impressions, SUM(engagements) AS engagements
  FROM bronze_social_events GROUP BY campaign_id, event_date
)
SELECT c.campaign_id, c.account_id, c.region, s.day,
       s.spend_usd, COALESCE(r.revenue_usd, 0) AS revenue_usd, COALESCE(r.refunded_sales, 0) AS refunded_sales,
       COALESCE(so.impressions, 0) AS impressions, COALESCE(so.engagements, 0) AS engagements
FROM spend s
JOIN silver_campaigns c USING (campaign_id)
LEFT JOIN revenue r ON r.campaign_id = s.campaign_id AND r.day = s.day
LEFT JOIN social so ON so.campaign_id = s.campaign_id AND so.day = s.day;

CREATE OR REFRESH MATERIALIZED VIEW silver_invoices
COMMENT 'Subscription invoices with a late-payment flag'
AS
SELECT invoice_id, account_id, due_date, amount_usd, status, days_late, (days_late > 0) AS is_late
FROM bronze_invoices;

CREATE OR REFRESH MATERIALIZED VIEW silver_renewal_history
COMMENT 'Training rows for the renewal-risk model (features and observed outcome)'
AS
SELECT account_id, cycle, region, tier, avg_roi_180d, active_campaigns, revenue_trend_90d,
       late_invoice_rate, CAST(churned AS INT) AS churned
FROM bronze_renewal_history;
