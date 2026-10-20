-- Silver layer — cleaning and joins as materialized views (incremental refresh)

-- Latest creator per creator_id from CDC bronze
CREATE OR REFRESH MATERIALIZED VIEW silver_creators
COMMENT "Silver: latest known creator state derived from CDC events"
AS
WITH ranked AS (
  SELECT
    creator_id,
    payload.handle AS handle,
    payload.display_name AS display_name,
    payload.tier AS tier,
    payload.platform AS platform,
    payload.country AS country,
    payload.follower_count AS follower_count,
    payload.status AS status,
    payload.agent_email AS agent_email,
    payload.joined_at AS joined_at,
    payload.updated_at AS updated_at,
    op,
    seq,
    ROW_NUMBER() OVER (PARTITION BY creator_id ORDER BY seq DESC) AS rn
  FROM bronze_cdc_creators
)
SELECT creator_id, handle, display_name, tier, platform, country, follower_count, status, agent_email, joined_at, updated_at
FROM ranked
WHERE rn = 1 AND op != 'DELETE';

-- Latest campaign per campaign_id from CDC bronze
CREATE OR REFRESH MATERIALIZED VIEW silver_campaigns
COMMENT "Silver: latest known campaign state derived from CDC events, joined with brand info"
AS
WITH latest_camp AS (
  SELECT
    campaign_id,
    payload.account_id AS account_id,
    payload.name AS name,
    payload.start_date AS start_date,
    payload.end_date AS end_date,
    payload.budget_usd AS budget_usd,
    payload.status AS status,
    payload.created_at AS created_at,
    payload.updated_at AS updated_at,
    op,
    seq,
    ROW_NUMBER() OVER (PARTITION BY campaign_id ORDER BY seq DESC) AS rn
  FROM bronze_cdc_campaigns
)
SELECT
  c.campaign_id, c.account_id, b.brand_name, b.tier AS brand_tier,
  c.name, c.start_date, c.end_date, c.budget_usd, c.status, c.created_at, c.updated_at
FROM latest_camp c
LEFT JOIN bronze_salesforce_accounts b ON c.account_id = b.account_id
WHERE c.rn = 1 AND c.op != 'DELETE';

-- Brands enriched with primary contact (account exec). Dedupe bronze by account_id
-- (parquet folder has historical files from multiple data-gen runs; pick the newest by _ingest_ts).
CREATE OR REFRESH MATERIALIZED VIEW silver_brands
COMMENT "Silver: brand accounts joined with their account exec (dedup by account_id)"
AS
WITH dedup AS (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY account_id ORDER BY _ingest_ts DESC) AS rn
  FROM bronze_salesforce_accounts
)
SELECT
  a.account_id, a.brand_name, a.industry, a.country, a.arr_usd, a.tier, a.renewal_status,
  a.renewal_date, a.renewal_arr_usd, a.account_exec_email,
  c.first_name AS exec_first_name, c.last_name AS exec_last_name, c.email AS exec_email
FROM dedup a
LEFT JOIN (
  SELECT account_id, first_name, last_name, email,
         ROW_NUMBER() OVER (PARTITION BY account_id ORDER BY contact_id) AS rn
  FROM bronze_hubspot_contacts WHERE role = 'account_exec'
) c ON a.account_id = c.account_id AND c.rn = 1
WHERE a.rn = 1;

-- Daily TikTok engagement enriched with creator tier/platform
CREATE OR REFRESH MATERIALIZED VIEW silver_engagement
COMMENT "Silver: daily creator engagement enriched with tier"
AS
SELECT
  m.metric_id, m.creator_id, m.date,
  c.tier, c.platform, c.country, c.handle,
  m.impressions, m.engagements, m.video_views, m.comments
FROM bronze_tiktok_metrics m
LEFT JOIN silver_creators c ON m.creator_id = c.creator_id;

-- Daily ad spend enriched with campaign + brand
CREATE OR REFRESH MATERIALIZED VIEW silver_ad_spend
COMMENT "Silver: daily Google Ads spend enriched with campaign + brand"
AS
SELECT
  s.spend_id, s.campaign_id, s.date,
  c.account_id, c.brand_name, c.start_date AS campaign_start, c.end_date AS campaign_end, c.status AS campaign_status,
  s.clicks, s.impressions, s.spend_usd
FROM bronze_google_ads_spend s
LEFT JOIN silver_campaigns c ON s.campaign_id = c.campaign_id;

-- Revenue events enriched with brand + campaign
CREATE OR REFRESH MATERIALIZED VIEW silver_revenue
COMMENT "Silver: revenue events enriched with brand + campaign"
AS
SELECT
  r.transaction_id, r.kind, r.account_id AS revenue_account_id, r.creator_id, r.campaign_id,
  r.transaction_date, r.amount_usd, r.currency, r.status,
  c.brand_name AS campaign_brand, c.account_id AS campaign_account_id,
  b.brand_name AS direct_brand
FROM bronze_stripe_revenue r
LEFT JOIN silver_campaigns c ON r.campaign_id = c.campaign_id
LEFT JOIN bronze_salesforce_accounts b ON r.account_id = b.account_id;
