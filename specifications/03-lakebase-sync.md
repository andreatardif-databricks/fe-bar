# Lakebase — Autoscaling Postgres + Triggered Sync from Platinum

Skill: `databricks-lakebase-autoscale`. Read `SKILLS/databricks-lakebase-autoscale/SKILL.md` before implementing.

This spec covers the Lakebase resources (project, branch, endpoint, database) and the **triggered synced tables** that mirror Platinum into Postgres. The customer-facing API in `app/*.md` reads from these mirrored tables.

---

## A. Lakebase project, branch, endpoint, database

**All four DAB-declarable, except the database itself.** The bundle in `04-orchestration-dab.md` declares `postgres_projects` / `postgres_branches` / `postgres_endpoints`. The database is created by `app/scripts/lakebase_setup_db.sh` (run once, before `bundle deploy`) because there is no `postgres_databases` resource type yet (CLI v0.299.1).

### Project

- **Name**: `pulsar-influence` (dedicated project for this demo — Maya wants the renewal-week workload isolated).
- **`pg_version`: 17**.
- **`default_endpoint_settings.suspend_timeout_duration: 300s`** — endpoint scales to zero after 5 min idle. Triggered sync wakes it.
- **`lifecycle.prevent_destroy: true`** — protect against `bundle destroy` wiping the brand-client-facing database.

### Branch

- Default `production` branch is auto-created by the Lakebase CLI when the project is created. Do not declare a separate branch unless dev/staging are needed; the demo uses `production` only.

### Endpoint

- **Autoscaling range**: 0.5 → 4 CU (must satisfy max−min ≤ 16 CU).
- **HA**: off for the demo (incompatible with scale-to-zero — keep it off so the suspend story works).
- **Suspend**: `suspend_timeout_duration: 300s` (inherits from `default_endpoint_settings`).

### Database (created by script, not by DAB)

- **Database name**: `dbgen_pulsar_influence`.
- **Database resource ID** (used in the App `postgres` binding path): `db-dbgen-pulsar-influence` (underscores → hyphens, prefix `db-`).
- Created by `app/scripts/lakebase_setup_db.sh --db-name dbgen_pulsar_influence --project-id pulsar-influence --database-id db-dbgen-pulsar-influence` BEFORE `databricks bundle deploy`.
- After `bundle deploy`, run `app/scripts/lakebase_grant_app_credential.sh --app-name pulsar-influence-api --project-id pulsar-influence --db-name dbgen_pulsar_influence` so the App SP gets `CREATE` + `USAGE` on schema `public` (the binding only grants `CONNECT`).

### Variables in the bundle

```yaml
variables:
  lakebase_project_id:    { default: "pulsar-influence" }
  lakebase_branch_id:     { default: "production" }
  lakebase_database_name: { default: "dbgen_pulsar_influence" }
  lakebase_database_id:   { default: "db-dbgen-pulsar-influence" }
```

---

## B. Triggered synced tables (Platinum → Lakebase)

Use **Lakeflow Connect's reverse synced-database feature** (not Lakehouse Sync — that's the other direction). Each Platinum table maps to a Postgres table in `dbgen_pulsar_influence` with **MODE = TRIGGERED**.

### Synced tables

| Source (Delta, in pipeline) | Target Postgres table | Primary key | Mode |
|---|---|---|---|
| `platinum_creator_360` | `public.creators` | `creator_id` | TRIGGERED |
| `platinum_campaign_360` | `public.campaigns` | `campaign_id` | TRIGGERED |
| `platinum_brand_360` | `public.brands` | `account_id` | TRIGGERED |

Each synced table has the same column shape as its source, plus a `_synced_at TIMESTAMPTZ` column (writer-managed) so the freshness-inspector endpoint can show end-to-end lag.

### Trigger contract

The synced tables are **not on a continuous schedule**. They run when the orchestration job (`04-orchestration-dab.md`) explicitly fires them via SDK / CLI after the SDP pipeline update completes. This is the "triggered, not continuous" beat in the demo:

```
SDP update finishes → job task: trigger sync → sync runs → endpoint warms → completes → endpoint suspends after 5 min
```

For the demo's live moment (creator status flip), the orchestration job is configured to run continuously every 60s in demo mode (`triggered_sync_interval = 60s` variable in the bundle), so the change reaches Lakebase within ~3 minutes of the CDC row landing.

### Lakebase schema (post-sync state)

The 3 mirror tables created by the synced-table setup. Maya never writes the schema by hand — the synced-table command derives Postgres types from Delta.

```
public.creators (
  creator_id          TEXT PRIMARY KEY,
  handle              TEXT,
  tier                TEXT,
  platform            TEXT,
  country             TEXT,
  status              TEXT,
  follower_count      BIGINT,
  attributed_revenue_30d_usd  NUMERIC,
  engagements_30d     BIGINT,
  ad_spend_30d_usd    NUMERIC,
  roi                 NUMERIC,
  agent_email         TEXT,
  updated_at          TIMESTAMPTZ,
  _synced_at          TIMESTAMPTZ
);

public.campaigns (
  campaign_id         TEXT PRIMARY KEY,
  account_id          TEXT,
  brand_name          TEXT,
  name                TEXT,
  start_date          DATE,
  end_date            DATE,
  budget_usd          NUMERIC,
  total_spend_usd     NUMERIC,
  total_revenue_usd   NUMERIC,
  roi                 NUMERIC,
  status              TEXT,
  updated_at          TIMESTAMPTZ,
  _synced_at          TIMESTAMPTZ
);

public.brands (
  account_id              TEXT PRIMARY KEY,
  brand_name              TEXT,
  tier                    TEXT,
  country                 TEXT,
  renewal_status          TEXT,
  renewal_date            DATE,
  renewal_arr_usd         NUMERIC,
  ytd_attributed_revenue_usd NUMERIC,
  active_campaigns        INT,
  renewal_health_score    INT,
  updated_at              TIMESTAMPTZ,
  _synced_at              TIMESTAMPTZ
);
```

### Indexes (created by the grant/setup script after first sync)

```
CREATE INDEX idx_creators_status_updated  ON public.creators (status, updated_at DESC);
CREATE INDEX idx_campaigns_account        ON public.campaigns (account_id, status);
CREATE INDEX idx_brands_renewal_status    ON public.brands (renewal_status, renewal_date);
```

API endpoints filter by `account_id`, `status`, `renewal_status` — all covered.

---

## C. Validation

| Check | Expected |
|---|---|
| Lakebase project listed | `databricks postgres list-projects` shows `pulsar-influence` |
| Endpoint suspends | After 5 min of no traffic, endpoint state = `SUSPENDED` |
| Synced tables created | `\dt public.*` in psql shows `creators`, `campaigns`, `brands` |
| Row counts roughly match Platinum | `SELECT COUNT(*) FROM public.creators` ≈ 5,000 |
| Late CDC reaches Lakebase within 3 min | Insert demo CDC row for `CR-00042` → wait ≤ 180s → `SELECT status FROM public.creators WHERE creator_id='CR-00042'` returns `paused` |
| Headline brands present | `SELECT brand_name, renewal_arr_usd FROM public.brands WHERE account_id IN ('ACC-00001'..'ACC-00005')` — 5 rows totaling ~$1.2M |
| `_synced_at` advances per sync run | Two consecutive triggered runs produce strictly increasing `MAX(_synced_at)` |

Update `resources.json.created_resources` with `lakebase_project_id`, `lakebase_project_slug`, and `lakebase_database`.
