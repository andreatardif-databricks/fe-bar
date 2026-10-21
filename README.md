# Traackr Renewal Radar

Creator-campaign intelligence for a creator-marketing platform's brand clients: which brands are about
to leave, which campaigns are burning budget, and what to do next. Everything runs on synthetic data.

**Customer:** Traackr, an influencer-marketing technology platform. **Decision:** where to intervene
before a brand's renewal, and where a brand should move spend, while a campaign is still running.

## Journey

```
Synthetic CRM, billing, ad, social, sales + CDC feeds  ->  UC volume (landing)
  -> Lakeflow (Auto Loader bronze -> silver -> gold -> platinum with AUTO CDC)
  -> MLflow renewal-risk model (UC-registered, champion alias)
  -> ai_gen actions grounded in campaign metrics AND the model's risk score
  -> Lakebase Autoscaling synced tables
  -> FastAPI Databricks App  +  curated Genie space
```

One job, `radar-daily-orchestration`, enforces the dependency order and ends with a freshness gate.

## Layout

| Path | Purpose |
|---|---|
| `src/generate/generate_sources.py` | Story-driven generator. Fails the job if the narrative drifts (see below) |
| `src/pipeline/` | Lakeflow SQL: `10_bronze`, `20_silver`, `30_gold`, `40_platinum` |
| `src/ml/train_renewal_risk.py` | Trains and registers the classifier; promotes only if it holds up |
| `src/ml/score_and_recommend.py` | Scores brands, runs `ai_gen`, writes the bottom-up `value_summary` |
| `src/ops/` | API catalog, row-level security, Lakebase sync, freshness gate |
| `app/radar/` | FastAPI app: scoped API keys, Genie (as the user), live model call, telemetry |
| `genie/radar_space.json` | The Genie space definition |
| `docs/` | Deck, AI build log |
| `evidence/` | Raw task output, API responses, Genie and model transcripts |

## What the generator enforces

The job fails unless all of these hold on the generated data:

- Creator tier fixes the follower band (nano 1K-10K ... macro 1M-5M) with no exceptions.
- Account ARR respects its tier band.
- One creator/campaign pair (`CR-00042` / `CMP-00137`) carries a seeded surge that totals **exactly $224,000**, and is the top revenue pair.
- Seasonality differs by region: NA/EMEA holiday, APAC Singles' Day and Lunar New Year, LATAM summer peak. NA holiday ROI must exceed off-season ROI.
- A 10-30% structurally inefficient campaign cohort exists (this is what the reallocation opportunity is built from).
- LATAM renewal churn exceeds NA in the model's training labels.

## Governance

- Quality expectations drop bad rows at bronze; table and column comments throughout.
- **Row-level security:** `brand_row_filter` (UC row filter) on `brand_radar` and `campaign_actions`,
  backed by the `brand_access` grants table. Lakebase cannot sync from a row-filtered table, so the sync
  reads unfiltered `*_serving` copies that only the pipeline owner can read.
- **API layer:** `portfolio` and `brand` key scopes. A brand key asking for another brand gets `404`.
- Every task writes a structured record to `run_log`; the app writes requests to `radar_app.request_log`.

## Run it

The app resource needs a Genie space, and the space needs the tables, so deploy in two stages.

```bash
# stage 1: data layer (schema, volume, pipeline, job)
mv resources/app.yml resources/app.yml.pending      # only if app.yml is present
databricks bundle deploy
databricks bundle run radar_daily                   # raw drop -> Lakebase-served tables

# stage 2: Genie space, then the app
databricks genie create-space <warehouse_id> "$(python -c 'import json;print(json.dumps(json.load(open("genie/radar_space.json"))))')" --title "Traackr Renewal Radar"
#   put the returned space id in databricks.yml (genie_space_id), then:
mv resources/app.yml.pending resources/app.yml
databricks bundle deploy && databricks bundle run radar_app
python scripts/grant_app_access.py --profile <profile>   # once, after the app's first deploy
python scripts/capture_evidence.py --run-id <job run id> --app-url <url> --warehouse <id> --catalog <catalog>
```

You also need a Lakebase Autoscaling project (`databricks postgres create-project renewal-radar-lb`).

Variables (catalog, schema, warehouse, Lakebase branch/endpoint/database, Genie space) are in
`databricks.yml`.

## Honest limits

- Synthetic data. The training labels carry a deliberately high churn rate (about 40%) so the model has
  signal to learn; it is not a market churn rate.
- The reallocation estimate assumes 30% of an underperformer's trailing spend can move to the regional
  benchmark and earn that ROI. That is a planning assumption to calibrate, not a forecast.
- The renewal-risk model is a demonstration of the pattern (train, register, score, feed the prompt), not a
  production-validated churn model.
