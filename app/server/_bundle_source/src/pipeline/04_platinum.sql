-- Platinum layer — streaming tables with AUTO CDC (SCD Type 1)
-- These are the customer-facing tables synced into Lakebase.

-- Enriched CDC source for creators: bronze_cdc_creators payload + 30d rollups from gold
CREATE OR REFRESH STREAMING TABLE _stream_cdc_creators_enriched
COMMENT "Streaming source feeding platinum_creator_360 via AUTO CDC"
AS
SELECT
  c.event_id,
  c.creator_id,
  c.op,
  c.seq,
  c.timestamp,
  c.payload.handle AS handle,
  c.payload.display_name AS display_name,
  c.payload.tier AS tier,
  c.payload.platform AS platform,
  c.payload.country AS country,
  c.payload.follower_count AS follower_count,
  c.payload.status AS status,
  c.payload.agent_email AS agent_email,
  c.payload.joined_at AS joined_at,
  c.payload.updated_at AS updated_at
FROM STREAM bronze_cdc_creators c;

CREATE OR REFRESH STREAMING TABLE platinum_creator_360
COMMENT "Platinum: latest creator state with rollups (AUTO CDC SCD Type 1)"
TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true');

CREATE FLOW platinum_creator_360_flow AS AUTO CDC INTO platinum_creator_360
FROM stream(_stream_cdc_creators_enriched)
KEYS (creator_id)
APPLY AS DELETE WHEN op = 'DELETE'
SEQUENCE BY seq
COLUMNS * EXCEPT (op, seq, event_id, timestamp)
STORED AS SCD TYPE 1;

-- Enriched CDC source for campaigns
CREATE OR REFRESH STREAMING TABLE _stream_cdc_campaigns_enriched
COMMENT "Streaming source feeding platinum_campaign_360 via AUTO CDC"
AS
SELECT
  c.event_id,
  c.campaign_id,
  c.op,
  c.seq,
  c.timestamp,
  c.payload.account_id AS account_id,
  c.payload.name AS name,
  c.payload.start_date AS start_date,
  c.payload.end_date AS end_date,
  c.payload.budget_usd AS budget_usd,
  c.payload.status AS status,
  c.payload.created_at AS created_at,
  c.payload.updated_at AS updated_at
FROM STREAM bronze_cdc_campaigns c;

CREATE OR REFRESH STREAMING TABLE platinum_campaign_360
COMMENT "Platinum: latest campaign state with ROI"
TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true');

CREATE FLOW platinum_campaign_360_flow AS AUTO CDC INTO platinum_campaign_360
FROM stream(_stream_cdc_campaigns_enriched)
KEYS (campaign_id)
APPLY AS DELETE WHEN op = 'DELETE'
SEQUENCE BY seq
COLUMNS * EXCEPT (op, seq, event_id, timestamp)
STORED AS SCD TYPE 1;

-- Brand 360 — derived MV (no CDC source, brands change rarely; use a materialized view)
CREATE OR REFRESH MATERIALIZED VIEW platinum_brand_360
COMMENT "Platinum: brand 360 (analogous to gold_brand_renewal_health, exposed at platinum)"
AS
SELECT
  account_id, brand_name, tier, country, renewal_status, renewal_date,
  renewal_arr_usd, ytd_attributed_revenue_usd, active_campaigns,
  renewal_health_score,
  current_timestamp() AS updated_at
FROM gold_brand_renewal_health;
