# Synthetic Data Design and Execution Evidence

## Executable generator

The complete generator is implemented in [`src/data_gen/generate.py`](src/data_gen/generate.py). It runs with Databricks Connect on serverless compute and writes Parquet source files into governed Unity Catalog Volumes. No customer records are used.

Each generated batch contains approximately:

| Source | Rows per batch | Purpose |
|---|---:|---|
| Salesforce accounts | 200 | Brand tier, ARR, renewal status, renewal date |
| HubSpot contacts | 800 | Account stakeholders and operating roles |
| Creator master / CDC | 5,000 plus late updates | Creator tier, platform, reach, lifecycle status |
| Campaign master / CDC | 2,000 plus late updates | Budget, lifecycle dates, operating status |
| Google Ads spend | ~50,000 | Daily clicks, impressions, and status-sensitive spend |
| TikTok metrics | 1,200,000 | Daily creator reach and engagement over 18 months |
| Stripe revenue | ~100,000 | Brand invoices and creator-attributed revenue |
| Contracts | 3,000 | Brand and creator agreements with expiry edge cases |

## Correlations encoded in the generator

The data is not independent random noise:

- Creator tier controls follower ranges: nano `1K–10K`, micro `10K–100K`, mid `200K–1M`, and macro `1M–5M`.
- Campaign status controls daily spend: active campaigns spend near daily budget, paused campaigns spend near zero, and ended campaigns retain historical spend.
- Account tier controls renewal ARR exposure: enterprise retains 100% of ARR, growth 60%, and starter 30%.
- Campaign dates span 18 months with 30–90 day durations, producing active, paused, and ended cohorts.
- Stripe creator-attribution rows join creators to campaigns, enabling governed ROI and creator-performance calculations.
- `CR-00042` (`@sofia.styles`) and `CMP-01337` (`Coach Spring Capsule`) contain a deliberate revenue-surge story rather than an accidental outlier.
- CDC feeds include ordered INSERT records plus late UPDATE and UPSERT records for paused, under-review, offboarded, and reactivated entities.
- Stripe includes paid, pending, and refunded transactions; contracts include active, expired, and terminated records.

## Actual governed-table profile

The following results were returned from the deployed Unity Catalog schema on October 20, 2026. Bronze counts include four generator refreshes retained by the streaming ingestion layer.

| Governed table | Actual rows |
|---|---:|
| `bronze_salesforce_accounts` | 800 |
| `bronze_hubspot_contacts` | 3,200 |
| `bronze_tiktok_metrics` | 4,800,000 |
| `bronze_google_ads_spend` | 243,460 |
| `bronze_stripe_revenue` | 401,380 |
| `bronze_s3_contracts` | 12,000 |
| `bronze_cdc_creators` | 20,024 |
| `bronze_cdc_campaigns` | 8,005 |
| `gold_campaign_roi` | 2,000 |
| `gold_creator_performance_daily` | 2,261,354 |
| `platinum_brand_360` | 200 |

Observed distributions:

```text
Account tiers: starter 388, growth 320, enterprise 92
Renewal status: renewed 484, up_for_renewal 252, upsell_candidate 56, churned 8
Creator tiers: nano 10,288, micro 7,868, mid 1,768, macro 100
Creator status: active 14,892, paused 4,608, under_review 500, offboarded 24
Stripe status: paid 370,812, pending 29,604, refunded 964
CDC operations: creator INSERT 20,000 / UPDATE 24; campaign INSERT 8,000 / UPDATE 4 / UPSERT 1
```

## Headline correlation and edge case

The designed `CR-00042` × `CMP-01337` relationship is visible in the executed data:

| Month | Creator revenue | Campaign share | Transactions |
|---|---:|---:|---:|
| June 2026 | $5,034 | $0 | 7 |
| July 2026 | $72,741 | $71,200 | 91 |
| August 2026 | $145,277 | $145,182 | 181 |
| September 2026 | $402,489 | $399,900 | 500 |
| October 2026 MTD | $174,287 | $173,719 | 215 |

The September peak is roughly 80× the pre-campaign baseline, and the campaign contributes 97–99% of the creator's revenue after launch. This deliberate relationship drives the campaign ROI, creator-performance, AI recommendation, renewal-risk, and live propagation stories used by the application.

## Reproducibility

The generator uses fixed seeds for categorical skews and deterministic IDs for accounts, creators, campaigns, contacts, transactions, and CDC sequences. Five headline brands and the headline creator/campaign are overridden deterministically so the business demo remains reproducible while the long-tail population retains realistic variation.
