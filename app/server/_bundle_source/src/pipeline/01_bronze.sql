-- Bronze layer — streaming tables reading parquet via Auto Loader
-- Source volumes:
--   /Volumes/ai_demo_gen/dev_andrea_tardif_demo_influencer_revenue_pipeline_modernized/raw_data/<src>/
--   /Volumes/ai_demo_gen/dev_andrea_tardif_demo_influencer_revenue_pipeline_modernized/cdc_events/{creators,campaigns}/

CREATE OR REFRESH STREAMING TABLE bronze_salesforce_accounts (
  CONSTRAINT account_id_not_null EXPECT (account_id IS NOT NULL) ON VIOLATION DROP ROW
)
COMMENT "Bronze: Salesforce brand accounts"
AS SELECT *, current_timestamp() AS _ingest_ts
FROM STREAM read_files(
  '/Volumes/ai_demo_gen/dev_andrea_tardif_demo_influencer_revenue_pipeline_modernized/raw_data/salesforce_accounts/',
  format => 'parquet'
);

CREATE OR REFRESH STREAMING TABLE bronze_hubspot_contacts (
  CONSTRAINT contact_id_not_null EXPECT (contact_id IS NOT NULL) ON VIOLATION DROP ROW
)
COMMENT "Bronze: HubSpot contacts"
AS SELECT *, current_timestamp() AS _ingest_ts
FROM STREAM read_files(
  '/Volumes/ai_demo_gen/dev_andrea_tardif_demo_influencer_revenue_pipeline_modernized/raw_data/hubspot_contacts/',
  format => 'parquet'
);

CREATE OR REFRESH STREAMING TABLE bronze_google_ads_spend (
  CONSTRAINT spend_id_not_null EXPECT (spend_id IS NOT NULL) ON VIOLATION DROP ROW
)
COMMENT "Bronze: Google Ads daily spend"
AS SELECT *, current_timestamp() AS _ingest_ts
FROM STREAM read_files(
  '/Volumes/ai_demo_gen/dev_andrea_tardif_demo_influencer_revenue_pipeline_modernized/raw_data/google_ads_spend/',
  format => 'parquet'
);

CREATE OR REFRESH STREAMING TABLE bronze_tiktok_metrics (
  CONSTRAINT metric_id_not_null EXPECT (metric_id IS NOT NULL) ON VIOLATION DROP ROW
)
COMMENT "Bronze: TikTok daily metrics"
AS SELECT *, current_timestamp() AS _ingest_ts
FROM STREAM read_files(
  '/Volumes/ai_demo_gen/dev_andrea_tardif_demo_influencer_revenue_pipeline_modernized/raw_data/tiktok_metrics/',
  format => 'parquet'
);

CREATE OR REFRESH STREAMING TABLE bronze_stripe_revenue (
  CONSTRAINT transaction_id_not_null EXPECT (transaction_id IS NOT NULL) ON VIOLATION DROP ROW
)
COMMENT "Bronze: Stripe revenue (brand invoices + creator-attribution)"
AS SELECT *, current_timestamp() AS _ingest_ts
FROM STREAM read_files(
  '/Volumes/ai_demo_gen/dev_andrea_tardif_demo_influencer_revenue_pipeline_modernized/raw_data/stripe_revenue/',
  format => 'parquet'
);

CREATE OR REFRESH STREAMING TABLE bronze_s3_contracts (
  CONSTRAINT contract_id_not_null EXPECT (contract_id IS NOT NULL) ON VIOLATION DROP ROW
)
COMMENT "Bronze: S3 contract metadata"
AS SELECT *, current_timestamp() AS _ingest_ts
FROM STREAM read_files(
  '/Volumes/ai_demo_gen/dev_andrea_tardif_demo_influencer_revenue_pipeline_modernized/raw_data/s3_contracts/',
  format => 'parquet'
);

CREATE OR REFRESH STREAMING TABLE bronze_cdc_creators (
  CONSTRAINT event_id_not_null EXPECT (event_id IS NOT NULL) ON VIOLATION DROP ROW
)
COMMENT "Bronze: CDC change feed for creators (drives platinum AUTO CDC)"
AS SELECT *, current_timestamp() AS _ingest_ts
FROM STREAM read_files(
  '/Volumes/ai_demo_gen/dev_andrea_tardif_demo_influencer_revenue_pipeline_modernized/cdc_events/creators/',
  format => 'parquet'
);

CREATE OR REFRESH STREAMING TABLE bronze_cdc_campaigns (
  CONSTRAINT event_id_not_null EXPECT (event_id IS NOT NULL) ON VIOLATION DROP ROW
)
COMMENT "Bronze: CDC change feed for campaigns"
AS SELECT *, current_timestamp() AS _ingest_ts
FROM STREAM read_files(
  '/Volumes/ai_demo_gen/dev_andrea_tardif_demo_influencer_revenue_pipeline_modernized/cdc_events/campaigns/',
  format => 'parquet'
);
