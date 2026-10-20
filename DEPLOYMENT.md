# Pulsar Influence Co. — Deployment & Build Notes

End-to-end deployment of the Pulsar Influence Co. bundle into the `dbc-861f1864-b37c.cloud.databricks.com` workspace, plus the changes made to ship a Traackr-style developer portal on top of the same Lakebase mirror.

---

## 1. Target environment

| Item | Value |
|---|---|
| Workspace | https://dbc-861f1864-b37c.cloud.databricks.com (workspace id `7474646297979168`) |
| Databricks CLI profile | `pulsar-target` |
| SQL warehouse | `202b674cd44819fd` (Serverless Starter) |
| UC catalog | `ai_demo_gen` (created with default storage) |
| UC schema | `ai_demo_gen.dev_andrea_tardif_demo_influencer_revenue_pipeline_modernized` (dev-mode prefix applied automatically) |
| Lakebase instance | `pulsar-influence-lb` (CU_1, host `ep-rough-boat-d2k88jm8.database.us-east-1.cloud.databricks.com`) |
| Lakebase database | `dbgen_pulsar_influence` |
| App | `pulsar-influence-api` at https://pulsar-influence-api-7474646297979168.aws.databricksapps.com |
| App service principal | application_id `e7297dce-736d-478a-9ad8-29f713fd0451` |

---

## 2. What's running

### Data plane (deployed by `databricks bundle deploy`)

- **UC schema + volumes** — `raw_data/`, `cdc_events/` containing the synthetic source feeds
- **SDP pipeline** with four medallion layers:
  - Bronze: streaming tables reading parquet via Auto Loader (`src/pipeline/01_bronze.sql`)
  - Silver: materialized views for cleaning + joins (`02_silver.sql`)
  - Gold: analytics-ready aggregates (`03_gold.sql`)
  - Platinum: streaming tables with `AUTO CDC` for late-arriving creator + campaign changes (`04_platinum.sql`)
- **3 governed metric views** — `mv_creator_roi`, `mv_campaign_revenue`, `mv_renewal_health`
- **3 Lakebase synced tables** (reverse-ETL from Platinum):
  - `synced_creators` (TRIGGERED, mirrors `platinum_creator_360`)
  - `synced_campaigns` (TRIGGERED, mirrors `platinum_campaign_360`)
  - `synced_brands` (SNAPSHOT, mirrors `platinum_brand_360`)
- **2 Jobs**:
  - `pulsar_setup` — one-time: Lakebase instance + synced tables + metric views
  - `pulsar_orchestration` — day-2: regen data → run pipeline → trigger sync → freshness check

### Serving plane

- **Lakebase Postgres** instance `pulsar-influence-lb`, database `dbgen_pulsar_influence`
- **Customer-facing FastAPI** on Databricks Apps, reads from Lakebase views:
  - `GET /v1/brands/{brand_id}/renewal-health` — ARR + health score
  - `GET /v1/brands/{brand_id}/campaigns` — active/paused/ended campaigns
  - `GET /v1/brands/{brand_id}/creators` — creator roster
  - `GET /v1/freshness` — internal: lag between Platinum and Lakebase per table
  - `GET /v1/admin/api-keys` — list keys (OBO-auth)
  - `POST /v1/admin/api-keys` — create key (OBO-auth)
  - `PATCH /v1/admin/api-keys/{key}` — toggle active/revoked (OBO-auth)
  - `GET /v1/admin/brands` — deduped brand list for the create-key dropdown
- **Developer portal SPA** at `/` — Traackr-style docs + playground:
  - Sidebar API-key picker
  - Per-endpoint "Try it" panels (auto-fills `brand_id` from the picked key)
  - Architecture diagram tab (data-driven from `architecture.json`)
  - Admin → API keys with toggle + "+ New API key" modal

---

## 3. Deployment journey — what we hit and how it was fixed

### 3.1 Bundle to new workspace

- Authenticated `databricks auth login --host https://dbc-861f1864-b37c... --profile pulsar-target`
- Created the `ai_demo_gen` catalog via SQL (`databricks api post /api/2.0/sql/statements …` because `databricks catalogs create` failed on "Metastore storage root URL does not exist" — the workspace has Default Storage enabled and creation through the SDK requires going through SQL)
- Updated `databricks.yml`:
  - `warehouse_id` default → `202b674cd44819fd`
  - Added `presets.name_prefix: ''` on the `dev` target (kept dev mode otherwise)
- Updated hardcoded `WAREHOUSE_ID` constants in:
  - `src/deploy/create_metric_views.py`
  - `src/metric_views/create_metric_views.py`
  - `src/jobs/freshness_check.py`
  - `app/server/routes/freshness.py`
- **Dev-mode UC schema prefix**: `mode: development` adds `dev_<user_short_name>_` to UC objects regardless of `name_prefix` (which only affects job/pipeline display names). The hardcoded `SCHEMA = "demo_influencer_revenue_pipeline_modernized"` strings everywhere had to be rewritten to `dev_andrea_tardif_demo_influencer_revenue_pipeline_modernized` across `src/**/*.py`, `src/pipeline/01_bronze.sql`, and `app/server/routes/freshness.py` so the pipeline and SDK scripts pointed at the actual deployed schema.

### 3.2 Volume-empty pipeline failure

- `pulsar_setup` includes a `run_pipeline_first` task. On the first run the source volumes are empty, so Auto Loader fails with `No such file or directory: …/salesforce_accounts`.
- Workaround: run only the data generator first, then re-run `pulsar_setup`:
  ```bash
  databricks bundle run pulsar_orchestration --only generate_demo_data
  databricks bundle run pulsar_setup
  ```
- Synthetic data populates: 200 accounts, 800 contacts, 5K creators, 2K campaigns, ~50K ad-spend events, ~1.2M TikTok metrics, ~100K revenue events, ~3K contracts, plus CDC streams.

### 3.3 App-side issues (all the “Auth backend down” chain)

After `pulsar_setup` finished and the synced tables had data, the app deployed but every brand endpoint returned `{"detail":"Auth backend down: couldn't get a connection after 10.00 sec"}`. Several stacked bugs caused this — diagnosed by adding a temporary `/__debug` endpoint that exposed `os.environ` + raw psycopg connection errors:

| Layer | Bug | Fix |
|---|---|---|
| Python deps | `db.py` imports `from psycopg_pool import ConnectionPool` but `psycopg-pool` isn't in `app/requirements.txt` | Added `psycopg-pool>=3.2` |
| App resource binding | App had no `database` resource declared, so the Apps runtime didn't inject `PGHOST`/`PGUSER`/`PGPASSWORD` | Added `resources: - name: lakebase, database: { instance_name, database_name, permission: CAN_CONNECT_AND_CREATE }` to `databricks.yml` |
| Env var collision | `app.yaml` had `PGDATABASE: { valueFrom: lakebase }`, which the Apps runtime resolved to the resource *identifier* (the host string), not the database name. Connection string ended up with `dbname=ep-rough-boat-...` | Changed to a literal `PGDATABASE: "dbgen_pulsar_influence"` |
| Lakebase auth federation | The OAuth JWT minted by `generate_database_credential` is verified by the `databricks_auth` Postgres extension. The extension requires the role to be registered via `databricks_create_role(role, identity_type)`. A raw `CREATE ROLE "<sp-uuid>"` made the role exist but Lakebase still rejected the token with `password authentication failed` | Dropped the manually-created role (had to `REVOKE` SELECT on the three synced tables first to release `pg_shdepend` references), then `SELECT databricks_create_role('e7297dce-…', 'SERVICE_PRINCIPAL')` |
| Schema/table mismatch | `create_synced_tables.py` lands tables as `<catalog>.<schema>.synced_brands` etc. — in Postgres that materialized as `"dev_andrea_tardif_…".synced_brands`. The app code hardcodes `public.brands`, `public.campaigns`, `public.creators` | Created bridging views `public.brands`/`public.campaigns`/`public.creators` selecting from the synced tables; granted SELECT to the federated SP role |
| Instance permission | App SP didn't have `CAN_USE` on the Lakebase instance, so even with the role and federation the SDK call to `generate_database_credential` returned without a usable token | `databricks api patch /api/2.0/permissions/database-instances/pulsar-influence-lb` granting `CAN_USE` to the SP |
| App routes | `routes/brands.py` creators endpoint had `…replace("$1", "%s")` producing two `%s` placeholders but only one parameter; every call 500'd | Rewrote with explicit positional `%s` and `(status, status, limit)` |
| Browser caching | After fixes shipped, the user was still seeing the old JS rendering "Aurora Group (undefined)" because Starlette's `StaticFiles` doesn't send `Cache-Control: no-cache` | Subclassed `StaticFiles` as `NoCacheStaticFiles` to send `Cache-Control: no-cache, no-store, must-revalidate`; also added `?v=N` cache-bust query strings on the `<script>` and `<link>` tags |

---

## 4. Lakebase `public.api_keys` table

Created in `dbgen_pulsar_influence` to back the brand-client auth flow.

```sql
CREATE TABLE public.api_keys (
  api_key            text PRIMARY KEY,
  brand_id           text NOT NULL,
  brand_scope        text NOT NULL DEFAULT 'account_id'
                       CHECK (brand_scope IN ('all','brand_name','account_id')),
  label              text NOT NULL,
  is_active          boolean NOT NULL DEFAULT true,
  rate_limit_per_min int     NOT NULL DEFAULT 60,
  created_at         timestamptz NOT NULL DEFAULT now(),
  expires_at         timestamptz,
  last_used_at       timestamptz,
  use_count          bigint NOT NULL DEFAULT 0
);
CREATE INDEX api_keys_brand_id_idx ON public.api_keys (brand_id);
GRANT SELECT, INSERT, UPDATE, DELETE ON public.api_keys
  TO "e7297dce-736d-478a-9ad8-29f713fd0451";
```

### Brand scopes

The `brand_scope` column controls what URL `brand_id` values the key accepts:

| `brand_scope` | `brand_id` stores | Auth check |
|---|---|---|
| `all` | `*` (sentinel) | Any URL `brand_id` accepted — useful for internal back-office portals |
| `brand_name` | The brand name (e.g. `Aurora House`) | URL `brand_id` must belong to a brand with that `brand_name` — supports duplicate-name brands across multiple `account_id`s |
| `account_id` | `ACC-XXXXX` (legacy) | URL must match exactly |

### Seeded keys

| Key | Scope | Brand | Rate (rpm) |
|---|---|---|---|
| `pk_demo_coach` | brand_name | Coach | 120 |
| `pk_demo_coach_readonly` | brand_name | Coach | 30 |
| `pk_demo_revoked` | brand_name | Coach | 60 (inactive — demo of revocation) |
| `pk_demo_loreal` | brand_name | L'Oréal | 120 |
| `pk_demo_adidas` | brand_name | Adidas | 120 |
| `pk_demo_nike` | brand_name | Nike | 60 |
| `pk_demo_sephora` | brand_name | Sephora | 60 |

---

## 5. Developer portal (front-end)

Lives entirely inside the existing `pulsar-influence-api` Databricks App — no second app, no separate build step.

```
app/server/static/
├── index.html          # SPA shell (sidebar + sections, served from / via FileResponse)
├── styles.css          # Dark theme, Databricks-red accent, tier color palette
├── app.js              # Routing, key picker, Try-it, admin, architecture renderer
└── architecture.json   # Spec for the Architecture tab
```

### Tabs

| Tab | Content |
|---|---|
| Overview | Lede + KPIs (brand count, campaign count, creator count, sync-lag p95 from `/v1/freshness`) |
| Authentication | `X-Brand-API-Key` usage, error codes (401/403/503) |
| Architecture | Interactive 1720×710 diagram (see §6) |
| **Live Change Propagation** | Inject a single CDC event and watch it flow Raw → Bronze → Platinum → Lakebase → API with per-stage and total latency (see §7) |
| Renewal health / Campaigns / Creators | Endpoint docs + "Try it" panel (auto-fills `brand_id` from the active key) |
| Pipeline freshness | Internal endpoint that compares max `updated_at` Platinum vs Lakebase |
| Manage API keys | Full keys table (scope pills, account_id lists, toggle active/revoked, **+ New API key** modal) |

### "+ New API key" modal

- **Brand dropdown** is deduped (137 unique brand_names from the 200 generated accounts)
- Top option **★ All brands (unrestricted)** creates an `all`-scope key
- Selecting a name shows the list of `account_id`s the key will grant access to
- Optional **Generate** button mints `pk_demo_<slug>_<hex>` client-side via `crypto.getRandomValues`
- Optional **Expires at** datetime
- Server validates brand existence + key regex + unique constraint; returns `409` on duplicate, `400` on bad input

### Caching

- `NoCacheStaticFiles` subclass on `/static/*` sends `Cache-Control: no-cache, no-store, must-revalidate`
- `/` (the SPA shell) gets the same header on the `FileResponse`
- `<script>` and `<link>` tags use `?v=N` query strings so older browsers still pick up new builds

---

## 6. Architecture diagram (data-driven, absolute positioning)

The Architecture tab renders entirely from `app/server/static/architecture.json`. No code change is needed to add/move nodes — edit the JSON and refresh.

### Spec shape

```jsonc
{
  "layout": { "width": 1720, "height": 710, "node_width": 200, "node_height": 64 },
  "nodes": [
    { "id": "src-salesforce", "label": "Salesforce", "icon": "inputData",
      "tier": "source", "desc": "Accounts", "x": 0, "y": 0 },
    // …14 more nodes with absolute x/y
  ],
  "edges": [
    { "from": "src-salesforce", "to": "ingest", "animated": true },
    { "from": "platinum", "to": "lakebase", "label": "Triggered Sync", "animated": true },
    // …
  ],
  "groups": [ /* SDP Pipeline (DAB) dashed band */ ],
  "bars":   [ /* Lakeflow Jobs + Unity Catalog cross-cutting bands */ ]
}
```

### Renderer

- Builds a 1720×710 `.arch-stage` with each node positioned absolutely
- Applies `transform: scale(container_width / 1720)` so the diagram fits any container width while keeping edge alignment perfect (edges are drawn in the same coordinate system, so scaling preserves correctness)
- **Edge anchors** picked per-edge based on relative position: `right→left` for horizontal flow, `bottom→top` when the destination is below in the same column, etc. Cubic Béziers with control points 55% of dx/dy
- **Edge labels** rendered as SVG text with a pill background (`<rect rx=4>`), de-overlapped by nudging y by 22px when within 80×18px of an already-placed label
- **Animated edges** (the data-flow path) use a dashed stroke with a `stroke-dashoffset` keyframe animation (marching ants)

### Tier color palette

| Tier | Border | Used for |
|---|---|---|
| `source` / `consumer` | #4ea1ff | Salesforce/HubSpot/etc, Users |
| `ingest` | #00b8d4 | Lakeflow Connect |
| `bronze` | #b87333 | Bronze Layer |
| `silver` | #c0c0c0 | Silver Layer |
| `gold` | #e0b840 | Gold Layer |
| `streaming` | #00a972 | Platinum Layer (AUTO CDC) |
| `analytics` | #9b8cff | Metric Views, Customer-Facing API |
| `compute` | var(--accent) (Databricks red) | Lakebase |

---

## 7. Live Change Propagation tab

Inject a single CDC event into the `cdc_events/` volume and observe it flow through every stage to the customer-facing API, with per-stage and total latency measured.

### Endpoints (all OBO-auth, like the API-keys admin)

| Method + path | Purpose |
|---|---|
| `GET /v1/admin/propagation/targets?brand_id={id}` | Returns Maya creators + the brand's campaigns + the allowlisted fields/values to populate the UI dropdowns. |
| `POST /v1/admin/propagation/changes` | Body: `{entity, entity_id, field, new_value, brand_id?}`. Writes a single CDC parquet to the volume, persists a tracking row, triggers SDP + the matching synced-table pipeline directly via SDK (never `generate_demo_data`), returns `change_id` + `t_raw` + run ids. |
| `GET /v1/admin/propagation/changes/{change_id}/status` | Stage-by-stage observer. First poll where each stage is satisfied stamps `t_bronze` / `t_platinum` / `t_lakebase` / `t_api` into the tracking table. If `t_platinum` is observed before `t_lakebase`, the endpoint automatically re-triggers the synced-table pipeline once (`sync_retriggered=true`), because the original sync run can race ahead of the SDP run. Returns latencies and `complete: true` once API is reached. |

### Allowlisted change set (intentionally narrow)

Demoable changes the dropdown allows:

| Entity | Field | Allowed values |
|---|---|---|
| creator | `display_name` | any string |
| creator | `status` | `active`, `paused`, `under_review`, `offboarded` |
| creator | `tier` | `nano`, `micro`, `mid`, `macro` |
| campaign | `status` | `active`, `paused`, `ended` |
| campaign | `name` | any string |

`follower_count` and `budget_usd` are intentionally not in the dropdown because they cascade into derived Gold aggregates and the demo measures pure CDC flow, not downstream recompute.

### CDC contract that the route writes against

The route writes a 1-row parquet file under `cdc_events/{creators|campaigns}/change_<uuid>.parquet`. Schema is reproduced verbatim from `DESCRIBE bronze_cdc_creators` / `bronze_cdc_campaigns`:

```
event_id    : string             "EV-CR-<seq>" or "EV-CMP-<seq>"
{creator_id|campaign_id} : string  -- AUTO CDC KEY
op          : string             "UPSERT"
seq         : bigint             MAX(seq) + 1 from bronze table (the AUTO CDC SEQUENCE BY column)
timestamp   : timestamp(us)
payload     : struct<...>        -- full row with the one field swapped; updated_at stamped to now()
```

The pipeline merges on `(KEYS, max-seq)`, so the new event always wins.

### Lakebase tracking table

```sql
public.propagation_changes (
  change_id, entity, entity_id, field, old_value, new_value, brand_id,
  sequence_no, run_id, sync_run_id, sync_retriggered,
  t_raw, t_bronze, t_platinum, t_lakebase, t_api,
  error, created_at
)
```

Each status poll observes only stages that are still null and stamps timestamps once. Polls after `complete: true` skip all warehouse / Lakebase / self-HTTP work.

### Front-end (`#propagation` section)

Sidebar entry under a new **Live demo** nav group, between Architecture and Brand endpoints.

- Control panel: entity toggle (Creator / Campaign), entity dropdown (auto-scoped to the active key's brand), field dropdown, new-value input (text box or enum select depending on field), `Current <field>: <bold>` hint, **Push change** button.
- Stage tracker: 5 nodes in a horizontal pipeline (Raw, Bronze, Platinum, Lakebase, API), with an in-pipeline **"Silver / Gold MV refresh, in-pipeline, not separately timed"** band between Bronze and Platinum (materialized views share their refresh window with the SDP update and have no per-row timestamp). Each node lights in its tier color when reached; the edge from the leading-edge stage animates marching-ants.
- Latency readout: per-stage ms below each node, plus prominent **Total end-to-end** plus SDP run id, sync run id, and live status (`in flight` / `sync re-triggered` / `complete`).
- Before/After panels: pre-push API JSON (old value highlighted red) and post-complete API JSON (new value highlighted green), both filtered to the single entity.

### Required SP grants (Phase 1 of this build, applied 2026-05-29)

| Object | Grant |
|---|---|
| `ai_demo_gen` catalog | `USE CATALOG` |
| `ai_demo_gen.dev_andrea_tardif_demo_influencer_revenue_pipeline_modernized` schema | `USE SCHEMA` |
| `bronze_cdc_creators`, `bronze_cdc_campaigns` | `SELECT` |
| `platinum_creator_360`, `platinum_campaign_360` | `SELECT` |
| `cdc_events` volume | `READ VOLUME`, `WRITE VOLUME` |
| SDP pipeline `93708933-…` | `CAN_RUN` |
| Synced pipelines `08f648b7-…` (creators), `b65659f6-…` (campaigns) | `CAN_RUN` |
| Lakebase `public.propagation_changes` | `SELECT, INSERT, UPDATE` |

### Real measured latencies (2026-05-30 from the live deployment)

| Run | Total | Bronze (from raw) | Platinum (from bronze) | Lakebase (from platinum) | API (from lakebase) | Notes |
|---|---|---|---|---|---|---|
| CR-00450 `display_name` flip | 2m 45.8s | 59.5 s | 57.4 s | 48.8 s | 63 ms | sync re-triggered once |
| CMP-01843 `status` active→paused | 2m 29.8s | 83.6 s | 2.3 s | 63.8 s | 74 ms | bronze + platinum observed on same poll (warm pipeline) |

End-to-end cold-start is ~2.5 to 3 minutes; back-to-back warm runs trim toward ~1.5 minutes. The API stage itself is sub-100ms in every observed run because Lakebase reads are millisecond-level.

### Gotcha: synced-table race

The change-injection POST fires the SDP pipeline and the synced-table pipeline in parallel (to minimise total latency). The synced-table pipeline reads from `platinum_*_360`, so if it starts before the SDP update is finished, it sees the *old* row and the API never reflects the new value. The status endpoint detects this case (`t_platinum != null AND t_lakebase == null AND sync_retriggered == false`) and re-triggers the synced pipeline once. `sync_retriggered` is sticky so we never thrash.

---

## 8. Files changed (under bundle root)

### Bundle config

- `databricks.yml` — warehouse_id default, `presets.name_prefix: ''`, app `lakebase` database resource binding, `dab_instructions.md` reference unchanged

### Pipeline + jobs

- `src/pipeline/01_bronze.sql` — hardcoded volume paths point to the dev-prefixed schema
- `src/deploy/create_metric_views.py` — warehouse_id + schema
- `src/metric_views/create_metric_views.py` — warehouse_id + schema
- `src/deploy/create_synced_tables.py` — schema
- `src/deploy/setup_lakebase.py` — unchanged
- `src/data_gen/generate.py` — schema (paths in docstring + constants)
- `src/data_gen/fix_cdc.py` — schema
- `src/jobs/trigger_lakebase_sync.py` — schema
- `src/jobs/freshness_check.py` — warehouse_id + schema

### App

- `app/app.yaml` — `PGDATABASE` literal value, env vars
- `app/requirements.txt` — added `psycopg-pool>=3.2`, `pyarrow>=17.0` (for the propagation parquet writer)
- `app/server/main.py` — registers admin + **propagation** routers, mounts `NoCacheStaticFiles`, serves `index.html` at `/`
- `app/server/db.py` — unchanged
- `app/server/auth.py` — rewritten for `brand_scope`-aware validation, telemetry bumps
- `app/server/routes/admin.py` — **new** (list keys, create key, toggle active, list brands)
- `app/server/routes/propagation.py` — **new** (Live Change Propagation: targets, changes, status)
- `app/server/routes/brands.py` — creators SQL placeholder bug fix
- `app/server/routes/freshness.py` — warehouse_id + schema
- `app/server/static/index.html` — SPA shell + modal markup + Live Change Propagation section
- `app/server/static/styles.css` — Live Change Propagation styles (`.prop-*`)
- `app/server/static/app.js` — adds propagation tab controller, polling, before/after panels
- `app/server/static/architecture.json` — absolute-positioned diagram spec

### Notes

- The `dab_instructions.md` and `architecture.md` files in the bundle root are the original artifacts. `architecture.md` is also valid JSON; the UI loads a separate copy at `app/server/static/architecture.json` so we can iterate on the visualization independently.
- `resources.json` reflects the *original* workspace IDs — not updated to the new workspace since this file is build-output metadata.

---

## 9. Operational quick-reference

```bash
# Set profile once
export DATABRICKS_CONFIG_PROFILE=pulsar-target

# Validate + deploy
databricks bundle validate
databricks bundle deploy

# First-time bring-up (in order)
databricks bundle run pulsar_orchestration --only generate_demo_data
databricks bundle run pulsar_setup
# Grant the SP a federated Postgres role (one-time):
#   1. databricks api patch /api/2.0/permissions/database-instances/pulsar-influence-lb \
#        --json '{"access_control_list":[{"service_principal_name":"<sp-uuid>","permission_level":"CAN_USE"}]}'
#   2. Connect to the database as the workspace admin and run:
#        SELECT databricks_create_role('<sp-uuid>', 'SERVICE_PRINCIPAL');
#        GRANT USAGE ON SCHEMA public TO "<sp-uuid>";
#        GRANT USAGE ON SCHEMA "<prefixed-schema>" TO "<sp-uuid>";
#        GRANT SELECT ON ALL TABLES IN SCHEMA "<prefixed-schema>" TO "<sp-uuid>";
#        CREATE OR REPLACE VIEW public.brands AS SELECT * FROM "<prefixed-schema>".synced_brands;
#        CREATE OR REPLACE VIEW public.campaigns AS SELECT * FROM "<prefixed-schema>".synced_campaigns;
#        CREATE OR REPLACE VIEW public.creators AS SELECT * FROM "<prefixed-schema>".synced_creators;
#        GRANT SELECT ON public.brands, public.campaigns, public.creators TO "<sp-uuid>";
databricks bundle run pulsar_app

# Day-2: refresh data + pipeline + sync + freshness SLA check
databricks bundle run pulsar_orchestration

# Get the app SP id for grants:
databricks apps get pulsar-influence-api --output json | jq -r '.service_principal_client_id'

# Tail app logs (browser, WebSocket UI):
open https://pulsar-influence-api-7474646297979168.aws.databricksapps.com/logz

# Add cache-busted refresh on the UI (no-cache headers are in place — should not be needed):
# Cmd+Shift+R / Ctrl+Shift+R
```

### Gotchas worth flagging for future deploys

1. **Run `generate_demo_data` BEFORE `pulsar_setup`.** The setup job's pipeline-first task reads from the source volumes; if they're empty, it fails on Auto Loader's missing-path error.
2. **App `database` resource binding is required** — without it the Apps runtime won't inject Postgres env vars, and the app's SDK fallback path can't reach Lakebase from inside the Apps container.
3. **Don't use `valueFrom:` for `PGDATABASE`** in `app.yaml` — it resolves to the resource identifier (host), not the database name. Use a literal value.
4. **Manually creating Postgres roles doesn't enroll them in Lakebase auth federation.** Always use `SELECT databricks_create_role('<id>', 'SERVICE_PRINCIPAL')`.
5. **Dev-mode UC prefix is automatic** and not disabled by `presets.name_prefix: ''`. If you redeploy as a different user, the schema name changes and the hardcoded paths in `01_bronze.sql` + the SDK scripts need updating. Production target should use `mode: production` to avoid this.
6. **No-cache headers + `?v=N` query strings** are wired up — but if you ever stop using `NoCacheStaticFiles`, bump the version on every UI deploy.
