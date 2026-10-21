-- Bronze: append-only Auto Loader ingestion of the landing volume.
-- ${radar.landing} is injected from the pipeline configuration in databricks.yml.
-- Rows missing their business key are dropped at the door and counted in the event log.

CREATE OR REFRESH STREAMING TABLE bronze_accounts (
  CONSTRAINT has_account_id EXPECT (account_id IS NOT NULL) ON VIOLATION DROP ROW
)
COMMENT 'Traackr brand accounts as exported from the CRM'
AS SELECT *, _metadata.file_path AS _source_file, current_timestamp() AS _ingested_at
FROM STREAM read_files('${radar.landing}/accounts/', format => 'parquet');

CREATE OR REFRESH STREAMING TABLE bronze_invoices (
  CONSTRAINT has_invoice_id EXPECT (invoice_id IS NOT NULL) ON VIOLATION DROP ROW
)
COMMENT 'Monthly subscription invoices from billing'
AS SELECT *, _metadata.file_path AS _source_file, current_timestamp() AS _ingested_at
FROM STREAM read_files('${radar.landing}/invoices/', format => 'parquet');

CREATE OR REFRESH STREAMING TABLE bronze_ad_spend (
  CONSTRAINT has_spend_id EXPECT (spend_id IS NOT NULL) ON VIOLATION DROP ROW,
  CONSTRAINT non_negative_spend EXPECT (spend_usd >= 0) ON VIOLATION DROP ROW
)
COMMENT 'Daily paid-media spend by campaign'
AS SELECT *, _metadata.file_path AS _source_file, current_timestamp() AS _ingested_at
FROM STREAM read_files('${radar.landing}/ad_spend/', format => 'parquet');

CREATE OR REFRESH STREAMING TABLE bronze_social_events (
  CONSTRAINT has_event_id EXPECT (event_id IS NOT NULL) ON VIOLATION DROP ROW
)
COMMENT 'Daily creator impressions and engagements per campaign'
AS SELECT *, _metadata.file_path AS _source_file, current_timestamp() AS _ingested_at
FROM STREAM read_files('${radar.landing}/social_events/', format => 'parquet');

CREATE OR REFRESH STREAMING TABLE bronze_creator_sales (
  CONSTRAINT has_sale_id EXPECT (sale_id IS NOT NULL) ON VIOLATION DROP ROW
)
COMMENT 'Attributed storefront sales per campaign and creator'
AS SELECT *, _metadata.file_path AS _source_file, current_timestamp() AS _ingested_at
FROM STREAM read_files('${radar.landing}/creator_sales/', format => 'parquet');

CREATE OR REFRESH STREAMING TABLE bronze_renewal_history (
  CONSTRAINT has_cycle_id EXPECT (cycle_id IS NOT NULL) ON VIOLATION DROP ROW
)
COMMENT 'Prior renewal cycles with outcomes; labels for the renewal-risk model'
AS SELECT *, _metadata.file_path AS _source_file, current_timestamp() AS _ingested_at
FROM STREAM read_files('${radar.landing}/renewal_history/', format => 'parquet');

CREATE OR REFRESH STREAMING TABLE bronze_creator_cdc (
  CONSTRAINT has_event_id EXPECT (event_id IS NOT NULL) ON VIOLATION DROP ROW
)
COMMENT 'Ordered change feed for the creator roster'
AS SELECT *, _metadata.file_path AS _source_file, current_timestamp() AS _ingested_at
FROM STREAM read_files('${radar.landing}/creator_cdc/', format => 'parquet');

CREATE OR REFRESH STREAMING TABLE bronze_campaign_cdc (
  CONSTRAINT has_event_id EXPECT (event_id IS NOT NULL) ON VIOLATION DROP ROW
)
COMMENT 'Ordered change feed for campaign definitions and budgets'
AS SELECT *, _metadata.file_path AS _source_file, current_timestamp() AS _ingested_at
FROM STREAM read_files('${radar.landing}/campaign_cdc/', format => 'parquet');
