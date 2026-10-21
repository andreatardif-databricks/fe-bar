# Traackr Influencer Revenue Decision Platform

## Start Here: Verifiable AI and Runtime Proof

- `RAW_EXECUTION_TRANSCRIPT.md` — pasted successful job state, live model response, MLflow UC trace, and app OTEL UC row.

Directly reproduced execution excerpts:

```text
2026-10-20 17:14:46 "[prod] Pulsar — Daily Orchestration" TERMINATED SUCCESS
run_id=1013848902778635
generate_demo_data=SUCCESS → run_pipeline=SUCCESS → generate_ai_insights=SUCCESS → trigger_lakebase_sync=SUCCESS → freshness_check=SUCCESS
```

```text
Genie question: Which API endpoint shows renewal risk?
Genie status: COMPLETED
Genie answer: From api_endpoint_catalog, the API endpoint for renewal risk is GET /v1/brands/{brand_id}/renewal-health. It returns renewal health, ARR, revenue, and active campaign KPIs and uses X-Brand-API-Key authentication.
Conversation ID: 01f1cce7f0581fcdaed78469249b327a
```

```json
{"endpoint":"databricks-claude-haiku-5-5","recommendation":"Recommended action: Reallocate a portion of the remaining Holiday Glow budget toward the highest-performing creators and content formats, and pause spend on underperformers, to push ROI above the current 1.500.","usage":{"completion_tokens":95,"prompt_tokens":114,"total_tokens":209}}
```

The Genie interaction is stored twice in Unity Catalog: an MLflow `AGENT` span in `traackr_mlflow_otel_spans` and the full sanitized question/answer in `app_otel_logs`. OAuth tokens and user identity are never logged.

- Executable `ai_gen` SQL: [`AI_GEN_RECOMMENDATIONS.sql`](AI_GEN_RECOMMENDATIONS.sql)
- Orchestrated AI job: [`src/jobs/generate_ai_insights.py`](src/jobs/generate_ai_insights.py)
- Executable model-serving call: [`MODEL_ENDPOINT_RECOMMENDATION.py`](MODEL_ENDPOINT_RECOMMENDATION.py)
- Actual text run output: [`EXECUTION_EVIDENCE.md`](EXECUTION_EVIDENCE.md)
- Synthetic data logic, correlations, volumes, and executed profiles: [`SYNTHETIC_DATA.md`](SYNTHETIC_DATA.md)
- Full FE Bar requirement map: [`FE_BAR_SUBMISSION.md`](FE_BAR_SUBMISSION.md)
- Business presentation: [`presentation/traackr_fe_bar_deck.md`](presentation/traackr_fe_bar_deck.md)

This repository is an independently implemented Traackr prototype using synthetic data. The code, prompts, orchestration, deployment configuration, and captured execution output required to evaluate the build are included directly in the repository.

## Architecture

Production-shape Databricks Asset Bundle that deploys, in one `databricks bundle deploy`:

- A 4-layer SDP medallion pipeline (Bronze → Silver → Gold → Platinum) over 6 source feeds
- A governed semantic layer of 3 Metric Views (Unity Catalog) over Platinum/Gold
- A Lakebase (managed Postgres) instance and database
- 3 synced tables that mirror Platinum into Lakebase in TRIGGERED mode
- 2 Lakeflow Jobs: one-time setup and day-2 orchestration
- A customer-facing FastAPI on Databricks Apps with a built-in developer portal (docs, Try-it, key management, architecture diagram, and a Live Change Propagation tab that proves end-to-end freshness)

The bundle is workspace-portable. Configure 5 variables, run a handful of commands, and the whole stack lands in your workspace.

---

## What this bundle deploys

| Layer | Resource | File |
|---|---|---|
| UC infrastructure | catalog (pre-existing), schema, 2 volumes (`raw_data`, `cdc_events`) | `databricks.yml` |
| SDP pipeline | Bronze streaming tables, Silver/Gold materialized views, Platinum AUTO CDC streaming tables | `src/pipeline/01-04_*.sql` |
| Lakebase | Database Instance + logical database, 3 synced tables, 3 metric views | `src/deploy/*.py` |
| Orchestration | `pulsar_setup` (one-time), `pulsar_orchestration` (day-2) | `databricks.yml` jobs block + `src/jobs/*.py` |
| App | FastAPI brand-client API + developer portal (incl. Live Change Propagation) | `app/**` |

---

## Prerequisites

| | |
|---|---|
| Databricks workspace | Unity Catalog enabled, AWS or Azure |
| Databricks CLI | v0.220+ (`databricks --version`) |
| Workspace permissions | Workspace admin (you will create a catalog, a Lakebase instance, a Databricks App, and several pipelines/jobs) |
| Serverless SQL warehouse | Used for metric-view creation and the freshness/propagation status checks |
| Python | 3.11+ locally for the snapshot script |

---

## Variables to configure

All variables live in the top of `databricks.yml`. Either edit defaults or pass `--var=key=value` to each `bundle` command.

| Variable | Description | Example |
|---|---|---|
| `catalog` | UC catalog the schema/volumes/tables go into. Must already exist. | `traackr_demo` |
| `schema` | UC schema. Dev mode auto-prefixes (`dev_<user>_<schema>`). | `influencer_pipeline` |
| `warehouse_id` | Serverless SQL warehouse the deploy + admin paths talk to. | `1234567890abcdef` |
| `app_name` | Databricks App name (unique per workspace). | `traackr-influencer-api` |
| `lakebase_instance_name` | Lakebase Database Instance (legacy type; required for synced tables). | `traackr-lb` |
| `lakebase_database_name` | Postgres database inside the instance. | `traackr_influencer` |

After editing `databricks.yml`, also update the hardcoded `/Volumes/<catalog>/<schema>/...` paths in:

- `src/pipeline/01_bronze.sql` (Auto Loader source paths, 8 occurrences)
- `src/data_gen/generate.py` (`CATALOG`, `SCHEMA` constants near the top)
- `src/data_gen/fix_cdc.py`
- `src/deploy/*.py` (`CATALOG`, `SCHEMA`, `WAREHOUSE_ID`)
- `src/jobs/*.py` (`CATALOG`, `SCHEMA`, `WAREHOUSE_ID`)
- `src/metric_views/create_metric_views.py`
- `app/server/routes/freshness.py` (`SCHEMA`, `WAREHOUSE_ID`)
- `app/server/routes/propagation.py` (`SCHEMA`, `WAREHOUSE_ID`, plus the 3 pipeline IDs that Databricks generates on first deploy)
- `app/server/static/app.js` (`PROP_WS.host`, `PROP_WS.orgId`, `PROP_WS.sdpPipelineId`, `PROP_WS.syncPipelineId.{creator,campaign}`, `PROP_WS.lakebaseInstance`, `PROP_WS.lakebaseDatabase`) — these power the per-stage links in the Live Change Propagation tab

The hardcoding is intentional for demo readability. For a long-lived deployment, refactor to read these from a single config block.

---

## Deploy (first time)

```bash
# 0. CLI auth
databricks auth login --host https://<your-workspace>.cloud.databricks.com --profile traackr
export DATABRICKS_CONFIG_PROFILE=traackr

# 1. Create the catalog (one-time, if it does not exist)
databricks api post /api/2.0/sql/statements \
  --json '{"warehouse_id":"<WAREHOUSE_ID>","statement":"CREATE CATALOG IF NOT EXISTS traackr_demo"}'

# 2. Validate + deploy bundle resources (schema, volumes, pipeline, jobs, app definition)
databricks bundle validate
databricks bundle deploy

# 3. Populate source volumes FIRST (otherwise Bronze has nothing to read)
databricks bundle run pulsar_orchestration --only generate_demo_data

# 4. One-time setup: create the Lakebase instance, run the SDP pipeline once,
#    create the 3 synced tables, install the 3 metric views.
databricks bundle run pulsar_setup
```

At this point, the pipeline + Lakebase are live but the **app** still needs Postgres + Lakebase permissions on its service principal. The next two steps grant those.

```bash
# 5. Grant the app SP CAN_USE on the Lakebase instance, and federate a Postgres
#    role for it inside the database.

APP_SP=$(databricks apps get traackr-influencer-api --output json | jq -r '.service_principal_client_id')

# 5a. CAN_USE on the Lakebase instance
databricks api patch /api/2.0/permissions/database-instances/traackr-lb \
  --json "{\"access_control_list\":[{\"service_principal_name\":\"$APP_SP\",\"permission_level\":\"CAN_USE\"}]}"

# 5b. Federate a Postgres role for the SP, grant USAGE/SELECT on schemas and views.
#     Connect as workspace admin (psql / your tool of choice) and run:
#
#     SELECT databricks_create_role('<sp-uuid>', 'SERVICE_PRINCIPAL');
#     GRANT USAGE ON SCHEMA public TO "<sp-uuid>";
#     GRANT USAGE ON SCHEMA "<prefixed-schema>" TO "<sp-uuid>";
#     GRANT SELECT ON ALL TABLES IN SCHEMA "<prefixed-schema>" TO "<sp-uuid>";
#     CREATE OR REPLACE VIEW public.brands    AS SELECT * FROM "<prefixed-schema>".synced_brands;
#     CREATE OR REPLACE VIEW public.campaigns AS SELECT * FROM "<prefixed-schema>".synced_campaigns;
#     CREATE OR REPLACE VIEW public.creators  AS SELECT * FROM "<prefixed-schema>".synced_creators;
#     GRANT SELECT ON public.brands, public.campaigns, public.creators TO "<sp-uuid>";

# 6. (Optional, only if you want the Live Change Propagation tab) Grant the SP UC
#    permissions to read Bronze + Platinum and to write the cdc_events volume,
#    and CAN_RUN on the SDP + synced-table pipelines.

# UC grants:
databricks api post /api/2.0/sql/statements --json '{
  "warehouse_id":"<WAREHOUSE_ID>","statement":
  "GRANT USE CATALOG ON CATALOG traackr_demo TO `<sp-uuid>`;
   GRANT USE SCHEMA ON SCHEMA traackr_demo.<prefixed-schema> TO `<sp-uuid>`;
   GRANT SELECT ON TABLE traackr_demo.<prefixed-schema>.bronze_cdc_creators  TO `<sp-uuid>`;
   GRANT SELECT ON TABLE traackr_demo.<prefixed-schema>.bronze_cdc_campaigns TO `<sp-uuid>`;
   GRANT SELECT ON TABLE traackr_demo.<prefixed-schema>.platinum_creator_360  TO `<sp-uuid>`;
   GRANT SELECT ON TABLE traackr_demo.<prefixed-schema>.platinum_campaign_360 TO `<sp-uuid>`;
   GRANT READ VOLUME, WRITE VOLUME ON VOLUME traackr_demo.<prefixed-schema>.cdc_events TO `<sp-uuid>`"
}'

# Pipeline grants: SDP + the two synced-table refresh pipelines
for PIPE in <sdp_pipeline_id> <synced_creators_pipeline_id> <synced_campaigns_pipeline_id>; do
  databricks api patch "/api/2.0/permissions/pipelines/$PIPE" \
    --json "{\"access_control_list\":[{\"service_principal_name\":\"$APP_SP\",\"permission_level\":\"CAN_RUN\"}]}"
done

# 7. Lakebase table for propagation tracking
#    Connect as workspace admin and run the DDL from app/server/routes/propagation.py
#    (look for `CREATE TABLE IF NOT EXISTS public.propagation_changes` in this README's
#    public/api_keys + public/propagation_changes section below)

# 8. Deploy + start the app
databricks bundle run pulsar_app

# 9. (Optional, day-2) End-to-end refresh on a schedule
databricks bundle run pulsar_orchestration
```

When step 8 finishes, the developer portal is live at the URL the CLI prints, e.g.:
`https://traackr-influencer-api-<workspace-id>.<region>.databricksapps.com/`

Architecture (rendered live from `app/server/static/architecture.json`) is at `#architecture`. Live Change Propagation is at `#propagation`.

---

## Provisioning details

### `public.api_keys` (Lakebase)

The brand-client API authenticates against this table:

```sql
CREATE TABLE public.api_keys (
  api_key            text PRIMARY KEY,
  brand_id           text NOT NULL,
  brand_scope        text NOT NULL DEFAULT 'account_id'
                       CHECK (brand_scope IN ('all','brand_name','account_id')),
  label              text NOT NULL,
  is_active          boolean NOT NULL DEFAULT true,
  rate_limit_per_min int NOT NULL DEFAULT 60,
  created_at         timestamptz NOT NULL DEFAULT now(),
  expires_at         timestamptz,
  last_used_at       timestamptz,
  use_count          bigint NOT NULL DEFAULT 0
);
CREATE INDEX api_keys_brand_id_idx ON public.api_keys (brand_id);
GRANT SELECT, INSERT, UPDATE, DELETE ON public.api_keys TO "<app-sp-uuid>";
```

Seed at least one active key per brand so the developer portal's Try-it works. Use the `+ New API key` modal under `Admin → Manage API keys` to create more.

### `public.propagation_changes` (Lakebase, optional)

Required only if you enable the Live Change Propagation tab:

```sql
CREATE TABLE public.propagation_changes (
  change_id     text PRIMARY KEY,
  entity        text NOT NULL CHECK (entity IN ('creator','campaign')),
  entity_id     text NOT NULL,
  field         text NOT NULL,
  old_value     text,
  new_value     text,
  brand_id      text,
  sequence_no   bigint NOT NULL,
  run_id        text,
  sync_run_id   text,
  sync_retriggered boolean NOT NULL DEFAULT false,
  t_raw         timestamptz NOT NULL,
  t_bronze      timestamptz,
  t_platinum    timestamptz,
  t_lakebase    timestamptz,
  t_api         timestamptz,
  error         text,
  created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX propagation_changes_created_idx ON public.propagation_changes(created_at DESC);
GRANT SELECT, INSERT, UPDATE ON public.propagation_changes TO "<app-sp-uuid>";
```

### Brand views in Lakebase

The app reads from `public.brands`, `public.campaigns`, `public.creators`. Those are thin views over the synced tables that `pulsar_setup` lands in your prefixed schema:

```sql
CREATE OR REPLACE VIEW public.brands    AS SELECT * FROM "<prefixed-schema>".synced_brands;
CREATE OR REPLACE VIEW public.campaigns AS SELECT * FROM "<prefixed-schema>".synced_campaigns;
CREATE OR REPLACE VIEW public.creators  AS SELECT * FROM "<prefixed-schema>".synced_creators;
GRANT SELECT ON public.brands, public.campaigns, public.creators TO "<app-sp-uuid>";
```

---

## Verifying the deploy

1. **Architecture tab loads** with all 15 nodes positioned: `/#architecture`
2. **Try-it on `GET /v1/brands/{brand_id}/renewal-health`** returns a row (use any active key from `public.api_keys`)
3. **`GET /v1/freshness`** returns lag < 5 minutes for each of `creators`, `campaigns`, `brands`
4. **Live Change Propagation**: push a `creator.status` flip and watch all 5 stages light up; total end-to-end should land in 2–4 minutes on a warm warehouse

---

## Routine operations

```bash
# End-to-end day-2 refresh: regenerate data + run pipeline + trigger sync + freshness SLA
databricks bundle run pulsar_orchestration

# Re-snapshot the bundle viewer (run before EACH deploy if you've edited bundle code)
./scripts/snapshot_bundle.sh

# Push an app code change without re-running the whole bundle
databricks bundle deploy
databricks bundle run pulsar_app
```

---

## Customizing for your real data

1. Replace `src/data_gen/generate.py` with your own ingestion (Lakeflow Connect connectors, partner ETL, Kafka → bronze, etc.).
2. Match the CDC payload struct in `src/pipeline/01_bronze.sql` (the `bronze_cdc_*` tables) and `04_platinum.sql` (the AUTO CDC `KEYS` + `SEQUENCE BY`) to your real source feed.
3. Swap the API auth model in `app/server/auth.py` (replace the `pk_demo_*` keys with OAuth, HMAC, or your tenant's scheme).
4. Edit `app/server/routes/brands.py` and `entities.py` to expose the fields your customers actually need.
5. Update `app/server/static/architecture.json` to reflect your actual data flow (the renderer reads this file at runtime).

---

## Teardown

```bash
databricks bundle destroy --auto-approve
# Manual steps the destroy does not cover:
databricks database delete-database-instance <lakebase_instance_name>
databricks apps delete <app_name>
# (the App has prevent_destroy: true; the Lakebase instance is not bundle-managed)
```

---

## Known caveats

1. **`generate_demo_data` overwrites the source volumes.** Run it once for initial population; do not run it while demonstrating Live Change Propagation (it would erase the injected CDC event).
2. **Synced-table pipelines can race ahead of the SDP run.** The Live Change Propagation status endpoint detects this (platinum reached, lakebase still empty) and re-triggers the synced-table pipeline once. The orchestration job runs them sequentially via `depends_on`.
3. **Dev-mode UC schema prefix is automatic** (`dev_<user_short_name>_<schema>`). The 8 hardcoded paths in `src/pipeline/01_bronze.sql` and the SDK scripts will need to match. Either deploy in `prod` target (`mode: production`, no prefix) or rerun `scripts/snapshot_bundle.sh` and the hardcoded-path search in `Variables to configure` after each redeploy by a different user.
4. **Pipeline IDs are workspace-scoped** and are generated by Databricks on first deploy. After the first deploy, fetch them with `databricks bundle summary` and paste them into `app/server/routes/propagation.py` (`SDP_PIPELINE_ID`, `SYNCED_PIPELINE_ID`) and `app/server/static/app.js` (`PROP_WS.sdpPipelineId`, `PROP_WS.syncPipelineId`).
