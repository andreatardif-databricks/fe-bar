-- Platinum: serving tables. Change-captured entities use AUTO CDC (SCD Type 1) so the
-- Lakebase synced copies receive only changed rows. Change data feed is on for TRIGGERED sync.

CREATE OR REFRESH STREAMING TABLE platinum_creators (
  creator_id STRING, handle STRING, tier STRING, platform STRING, region STRING,
  follower_count BIGINT, status STRING
)
COMMENT 'Current creator roster, resolved from the ordered change feed'
TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true');

CREATE FLOW platinum_creators_flow AS AUTO CDC INTO platinum_creators
FROM STREAM(bronze_creator_cdc)
KEYS (creator_id)
APPLY AS DELETE WHEN op = 'DELETE'
SEQUENCE BY seq
COLUMNS creator_id, handle, tier, platform, region, follower_count, status
STORED AS SCD TYPE 1;

CREATE OR REFRESH STREAMING TABLE platinum_campaigns (
  campaign_id STRING, account_id STRING, name STRING, region STRING,
  start_date DATE, end_date DATE, budget_usd DOUBLE, status STRING
)
COMMENT 'Current campaign definitions, resolved from the ordered change feed'
TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true');

CREATE FLOW platinum_campaigns_flow AS AUTO CDC INTO platinum_campaigns
FROM STREAM(bronze_campaign_cdc)
KEYS (campaign_id)
APPLY AS DELETE WHEN op = 'DELETE'
SEQUENCE BY seq
COLUMNS campaign_id, account_id, name, region, start_date, end_date, budget_usd, status
STORED AS SCD TYPE 1;

CREATE OR REFRESH MATERIALIZED VIEW platinum_campaign_roi
COMMENT 'Campaign KPIs served to brand portals'
AS
SELECT campaign_id, account_id, brand_name, region, campaign_name, status,
       ROUND(spend_usd, 2) AS spend_usd, ROUND(revenue_usd, 2) AS revenue_usd, ROUND(roi, 3) AS roi,
       ROUND(roi_90d, 3) AS roi_90d, ROUND(engagement_rate, 4) AS engagement_rate, last_activity_date
FROM gold_campaign_performance;
