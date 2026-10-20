# Lakeflow — Synthetic Sources + 4-Layer SDP Pipeline (Bronze → Silver → Gold → Platinum)

## Shared Context (referenced by all other spec files)

**Catalog / schema**: `ai_demo_gen` / `demo_influencer_revenue_pipeline_modernized` (already created — see `resources.json`).

**Volumes**:
- `raw_data` — landing zone for the 6 synthetic source feeds (Auto Loader watches this).
- `cdc_events` — landing zone for late-arriving CDC events (drives the Platinum `AUTO CDC` flow).

**Time references** (anchored to runtime):
- `STORY_END_DATE = NOW`
- `STORY_START_DATE = NOW − 18 months`
- `RENEWAL_WINDOW_START = NOW + 1 week`, `RENEWAL_WINDOW_END = NOW + 4 weeks` (Q3 renewal week starts tomorrow)
- `SURGE_PEAK = NOW − 3 weeks`, `SURGE_DECAY_START = NOW − 2 weeks` (the recent creator-revenue surge that the old weekly batch missed)
- `LATE_CDC_WINDOW = NOW − 7 days … NOW − 1 hour` (5–10 CDC events backdated into this window so the Platinum `AUTO CDC` merge logic is visible during the demo)

**Headline brand accounts** (deterministic — drive the renewal-week story):

| account_id | brand_name | renewal_arr_usd | tier | renewal_status |
|---|---|---|---|---|
| ACC-00001 | Coach | 400000 | enterprise | up_for_renewal |
| ACC-00002 | L'Oréal | 320000 | enterprise | up_for_renewal |
| ACC-00003 | Adidas | 280000 | enterprise | up_for_renewal |
| ACC-00004 | Nike | 120000 | growth | upsell_candidate |
| ACC-00005 | Sephora | 80000 | growth | upsell_candidate |

`SUM(renewal_arr_usd) ≈ $1.2M` — the number in the story.

**Headline creator** (the late-CDC star of Act 4):

| creator_id | handle | tier | platform | status |
|---|---|---|---|---|
| CR-00042 | @sofia.styles | macro | tiktok | active → **paused** (CDC flips it during demo) |

`@sofia.styles` is the creator whose status flip Maya pushes through the pipeline live. She also drove the recent revenue surge for Coach (`SURGE_PEAK = NOW − 3 weeks`, ~3× her baseline weekly attributed revenue).

**Important reminder**: the build agent is generating PySpark / SQL on top of these specs. If exact numbers don't perfectly sum, that's fine — preserve the narrative shape (renewal ARR ≈ $1.2M, surge week is the visible peak, headline creator status flips end-to-end during the demo).

---

## A. Synthetic Data Generation

**Skill to use**: `databricks-synthetic-data-gen` — read `SKILLS/databricks-synthetic-data-gen/SKILL.md` before implementing.

**Python runtime**: use the pre-provisioned databricks-connect venv (Python 3.12, faker, numpy, pandas).

Write 6 source feeds as parquet under `{raw_data_volume}/<source>/` plus a CDC events folder under `{cdc_events_volume}/`:

| Source folder | Format | Rows | Notes |
|---|---|---|---|
| `salesforce_accounts/` | parquet | ~200 brand accounts | Industry, ARR, renewal_status, renewal_date. Includes the 5 headline brands above. |
| `hubspot_contacts/` | parquet | ~800 contacts | 3–5 contacts per account (account exec, marketing lead, billing). |
| `google_ads_spend/` | parquet | ~50K daily-campaign rows | One row per (campaign_id, date). Daily ad spend per campaign over 18 months. |
| `tiktok_metrics/` | parquet | ~1.2M rows | One row per (creator_id, date). Daily impressions / engagements / video_views per creator. |
| `stripe_revenue/` | parquet | ~100K transactions | Brand-pays-Pulsar invoices + creator-attributed revenue events. |
| `s3_contracts/` | parquet | ~3K contract metadata rows | One row per signed contract: account_id, creator_id (nullable), term_start, term_end, contract_value_usd, status. |
| `cdc_events/creators/` | parquet, append-only | ~5K historical + 5–10 demo events | Change-data-capture stream of creator status / tier changes. |
| `cdc_events/campaigns/` | parquet, append-only | ~3K historical + 3–5 demo events | CDC of campaign status / end-date amendments. |

### Entity counts and shape

- ~5,000 creators across 4 tiers: nano (50%), micro (30%), mid (15%), macro (5%). Platforms: TikTok 60%, Instagram 30%, YouTube 10%.
- ~2,000 campaigns over 18 months — each tied to one brand and 5–50 creators. Status: `active`, `paused`, `ended`. Budget $5K–$500K.
- Daily TikTok metrics per creator follow a Pareto: top 10% drive 70% of total engagement.
- Stripe revenue is bimodal: brand subscription invoices (monthly, $5K–$30K per brand) + creator-attributed transactions (per campaign, sum of attributed sales × take rate).

### Distributions

- **Brand renewals**: 60% renewed/active, 25% up_for_renewal in next 60 days (includes ACC-00001..5), 10% upsell_candidate, 5% churned.
- **Creator status mix**: 75% active, 15% paused, 7% under_review, 3% offboarded.
- **Campaign timing**: ~50 active in any given week. Some end-date amendments arrive 2–7 days late (the late-arriving updates the Platinum CDC handles).
- **Ad spend**: Google Ads spend correlates with campaign activity (spend up while campaign is `active`, drops to ~0 after `ended`).
- **Engagement**: TikTok daily impressions = `f(creator_tier, has_active_campaign, day_of_week)` with weekend lift × 1.4.

### The Event — what makes the story visible

1. **Renewal-week ARR pile-up**: `SUM(renewal_arr_usd)` for accounts with `renewal_status = 'up_for_renewal'` ≈ **$1.2M**, all dated within `RENEWAL_WINDOW_START..RENEWAL_WINDOW_END`. This is the at-risk number.

2. **Recent creator revenue surge** (`@sofia.styles` / CR-00042 working for Coach):
   - Baseline weekly attributed revenue: ~$8K (12 months prior).
   - 4 weeks ago: ~$12K.
   - 3 weeks ago (`SURGE_PEAK`): ~$48K — visible peak.
   - 2 weeks ago: ~$32K.
   - 1 week ago: ~$22K (decay).
   - Current week: ~$18K.
   - The OLD weekly ETL would have surfaced this peak only at next Monday's batch (already missed once because the Stripe export was malformed two weeks ago). The NEW pipeline catches it within minutes.

3. **Late CDC events for the demo** (timestamps in `LATE_CDC_WINDOW`):
   - `CR-00042` status: `active` → `paused` (the live demo flip).
   - `CR-00198` tier: `micro` → `mid` (a routine reclassification).
   - `CMP-01337` end_date moved out by +5 days (campaign extended).
   - `CR-00715` offboarded.
   - 2–4 additional benign creator-attribute updates so the auto-CDC merge isn't single-row trivial.

   These rows MUST land in `{cdc_events_volume}/...` AFTER the historical batch is generated, so the Platinum streaming tables actually exercise `AUTO CDC` during the demo.

### Source schemas (high level — column names are the contract)

**salesforce_accounts**: `account_id` (PK, ACC-NNNNN), `brand_name`, `industry`, `country`, `arr_usd`, `renewal_arr_usd`, `tier` (`enterprise|growth|starter`), `renewal_status` (`renewed|up_for_renewal|upsell_candidate|churned`), `renewal_date`, `account_exec_email`, `created_at`, `updated_at`.

**hubspot_contacts**: `contact_id` (PK, HUB-NNNNNN), `account_id` (FK), `first_name`, `last_name`, `email`, `role` (`account_exec|marketing_lead|billing`), `created_at`, `updated_at`.

**creators_master** (derived inside Bronze from the CDC events stream — there is NO standalone parquet for this; see CDC section below): `creator_id` (PK, CR-NNNNN), `handle`, `display_name`, `tier`, `platform`, `country`, `follower_count`, `status`, `agent_email`, `joined_at`, `updated_at`.

**campaigns_master** (also derived from CDC): `campaign_id` (PK, CMP-NNNNN), `account_id` (FK), `name`, `start_date`, `end_date`, `budget_usd`, `status` (`active|paused|ended`), `created_at`, `updated_at`.

**google_ads_spend**: `spend_id` (PK), `campaign_id` (FK), `date`, `clicks`, `impressions`, `spend_usd`.

**tiktok_metrics**: `metric_id` (PK), `creator_id` (FK), `date`, `impressions`, `engagements`, `video_views`, `comments`.

**stripe_revenue**: `transaction_id` (PK, TXN-NNNNNNNN), `kind` (`brand_invoice|creator_attribution`), `account_id` (FK, nullable), `creator_id` (FK, nullable), `campaign_id` (FK, nullable), `transaction_date`, `amount_usd`, `currency`, `status` (`paid|pending|refunded`).

**s3_contracts**: `contract_id` (PK, CTR-NNNNN), `account_id` (FK), `creator_id` (FK, nullable), `contract_type` (`brand_master|creator_engagement`), `term_start`, `term_end`, `contract_value_usd`, `signed_at`, `status` (`active|expired|terminated`).

**cdc_events/creators/** (append-only change feed): `event_id` (PK), `creator_id`, `op` (`INSERT|UPDATE|DELETE`), `seq` (monotonic int — drives `AUTO CDC` ordering), `timestamp`, `payload` (struct mirroring creators_master).

**cdc_events/campaigns/**: same shape, keyed on `campaign_id`.

> The CDC-driven entities (creators, campaigns) are intentionally **streamed in via the events folder** — they never land as a static parquet snapshot. Bronze is a streaming table reading the events; Silver/Gold compute the current-state via materialized views; Platinum applies `AUTO CDC` to keep the merged "latest state" table consistent. This is the showcase technique for the demo.

---

## B. SDP Pipeline — 4 Layers in One Pipeline

**Skill to use**: `databricks-spark-declarative-pipelines` — read `SKILLS/databricks-spark-declarative-pipelines/SKILL.md` before implementing.

Pipeline name: `pulsar_influence_revenue_pipeline`. Serverless. Channel: PREVIEW (for `AUTO CDC` syntax).

The pipeline source code lives in `src/pipeline/` in the project repo. **It will eventually be deployed via the Databricks Asset Bundle declared in `04-orchestration-dab.md`** — meaning the bundle's `resources.pipelines:` block points at this folder, and `databricks bundle deploy` creates the pipeline. During development the build agent may create the pipeline directly via the SDP skill; the bundle re-targets it later.

### Bronze — Streaming Tables (Auto Loader from `raw_data` + `cdc_events`)

One bronze streaming table per source. Auto Loader reads parquet from the matching folder; bronze tables are **streaming tables** (not MVs) so they handle continuous arrival.

| Bronze table | Source folder | Notes |
|---|---|---|
| `bronze_salesforce_accounts` | `raw_data/salesforce_accounts/` | Streaming table |
| `bronze_hubspot_contacts` | `raw_data/hubspot_contacts/` | Streaming table |
| `bronze_google_ads_spend` | `raw_data/google_ads_spend/` | Streaming table |
| `bronze_tiktok_metrics` | `raw_data/tiktok_metrics/` | Streaming table |
| `bronze_stripe_revenue` | `raw_data/stripe_revenue/` | Streaming table |
| `bronze_s3_contracts` | `raw_data/s3_contracts/` | Streaming table |
| `bronze_cdc_creators` | `cdc_events/creators/` | Streaming table — drives platinum CDC |
| `bronze_cdc_campaigns` | `cdc_events/campaigns/` | Streaming table — drives platinum CDC |

Standard expectations on each bronze table: `<primary_key> IS NOT NULL`. Capture `_ingest_ts = current_timestamp()`.

### Silver — Materialized Views (cleaning + joins)

| Silver MV | Inputs | Purpose |
|---|---|---|
| `silver_brands` | `bronze_salesforce_accounts` ⨝ `bronze_hubspot_contacts` (account_exec) | One row per brand with primary contact attached |
| `silver_creators` | `bronze_cdc_creators` (current state via `MAX(seq) PER creator_id`) | "Latest known creator" — used by gold; the demo also showcases the Platinum streaming-table version of this entity |
| `silver_campaigns` | `bronze_cdc_campaigns` (latest by seq) ⨝ `silver_brands` | Campaigns with brand attached |
| `silver_engagement` | `bronze_tiktok_metrics` ⨝ `silver_creators` | Daily engagement enriched with creator tier/platform |
| `silver_ad_spend` | `bronze_google_ads_spend` ⨝ `silver_campaigns` | Daily ad spend enriched with campaign + brand |
| `silver_revenue` | `bronze_stripe_revenue` ⨝ `silver_campaigns` (when campaign_id present) ⨝ `silver_brands` | Revenue events enriched with brand + campaign |

All silver MVs use **incremental refresh** (default for SDP MVs). Expectations: not-null primary keys, drop bad rows.

### Gold — Materialized Views (analytics-ready aggregates)

All gold MVs have `brand_name` and `tier` available as filter dimensions where the entity allows it.

| Gold MV | Grain | Key columns |
|---|---|---|
| `gold_creator_performance_daily` | (creator_id, date) | impressions, engagements, attributed_revenue_usd, ad_spend_usd, roi |
| `gold_campaign_roi` | (campaign_id) | brand_name, total_spend_usd, total_revenue_usd, roi, status, last_activity_date |
| `gold_brand_renewal_health` | (account_id) | brand_name, tier, renewal_status, renewal_arr_usd, renewal_date, active_campaigns, ytd_attributed_revenue_usd, **renewal_health_score** (0–100, derived: campaign volume + ROI + recency of activity) |

`renewal_health_score` is what the API returns for `GET /v1/brands/{brand_id}/renewal-health`.

### Platinum — Streaming Tables with `AUTO CDC`

This is the showcase layer. Each platinum table is created as an **empty streaming table**, then a separate `CREATE FLOW … AS AUTO CDC INTO …` statement applies the change feed against it. SDP figures out merge logic from the change feed.

| Platinum table | CDC source | Keys | Sequence column |
|---|---|---|---|
| `platinum_creator_360` | `bronze_cdc_creators` (op + payload) joined with current rollups from `gold_creator_performance_daily` (last 30d revenue, last 30d engagement) | `creator_id` | `seq` |
| `platinum_campaign_360` | `bronze_cdc_campaigns` joined with `gold_campaign_roi` | `campaign_id` | `seq` |
| `platinum_brand_360` | derived: a brand changes when any of its campaigns / creators / renewal fields change. Use a synthetic `seq = max(updated_at)` over the joined sources | `account_id` | `seq` |

`AUTO CDC` flow shape (functional, the build agent fills in syntax):

```sql
APPLY CHANGES INTO live.platinum_creator_360
FROM stream(live.bronze_cdc_creators)  -- enriched with the rollup join
KEYS (creator_id)
APPLY AS DELETE WHEN op = 'DELETE'
SEQUENCE BY seq
COLUMNS * EXCEPT (op, seq, event_id, _ingest_ts)
STORED AS SCD TYPE 1;
```

Type 1 (overwrite latest) — the demo doesn't need history of every change.

**Demo proof point**: when a new row lands in `cdc_events/creators/` for `CR-00042` with `op = UPDATE` and `payload.status = paused`, it must propagate through `bronze_cdc_creators` → `platinum_creator_360` (status flips) → triggered Lakebase sync → API response — within 3 minutes.

### Coherence contract

| Downstream consumer | Reads from | Required columns |
|---|---|---|
| `02-uc-governance.md` metric views | `platinum_creator_360`, `platinum_campaign_360`, `platinum_brand_360` | `creator_id`, `attributed_revenue_30d_usd`, `roi`, `renewal_arr_usd`, `renewal_health_score`, `tier`, `brand_name`, `status` |
| `03-lakebase-sync.md` triggered sync | All three platinum tables (the only ones synced to Lakebase) | All columns — Lakebase mirrors the platinum schema |
| `04-orchestration-dab.md` job | The pipeline as a whole | `pipeline_id` |
| `app/*.md` API endpoints | Read from Lakebase, never the lakehouse | Same columns, served from Postgres |

---

## C. Validation

Run after the first pipeline update succeeds. Every check must pass before declaring the pipeline ready.

| Check | Query (against `ai_demo_gen.demo_influencer_revenue_pipeline_modernized`) | Expected |
|---|---|---|
| All bronze populated | `SELECT COUNT(*) FROM bronze_<each>` | > 0 for all 8 bronze tables |
| Silver creators count | `SELECT COUNT(*) FROM silver_creators` | ≈ 5,000 |
| Silver campaigns count | `SELECT COUNT(*) FROM silver_campaigns` | ≈ 2,000 |
| Renewal ARR pile-up | `SELECT SUM(renewal_arr_usd) FROM gold_brand_renewal_health WHERE renewal_status = 'up_for_renewal'` | ≈ $1.2M |
| Headline creator surge | weekly `SUM(attributed_revenue_usd)` from `gold_creator_performance_daily` for `CR-00042` | Peak ≈ $48K at week of `SURGE_PEAK`, decay to ~$18K |
| Top renewal accounts present | `SELECT brand_name, renewal_arr_usd FROM gold_brand_renewal_health WHERE account_id IN ('ACC-00001'..'ACC-00005')` | All 5 present, summed ≈ $1.2M |
| Platinum populated | `SELECT COUNT(*) FROM platinum_creator_360`, `..campaign_360`, `..brand_360` | ~5,000 / ~2,000 / ~200 |
| Platinum reflects late CDC | `SELECT status FROM platinum_creator_360 WHERE creator_id='CR-00042'` after the CR-00042 demo CDC row lands | Returns `paused` (not `active`) |
| Platinum sequence integrity | `SELECT MAX(seq) FROM platinum_creator_360` | Equal to `MAX(seq)` in `bronze_cdc_creators` |

After validation, write the `pipeline_id` into `resources.json.created_resources.pipeline_id`.
