# Orchestration — Lakeflow Jobs + Databricks Asset Bundle

Skills: `databricks-jobs`, `databricks-bundles`. Read `SKILLS/databricks-bundles/SKILL.md` and `DEMO_SKILL_DIR/references/dab/dab.md` before implementing. This is the spec the build agent uses to author the bundle that ships **everything Maya deploys with one command**.

---

## A. The bundle's job — one workflow, four tasks

Job name: `pulsar_influence_revenue_job`. Declared under `resources.jobs:` in `databricks.yml`.

### Tasks (run sequentially)

| Order | Task key | Type | Purpose |
|---|---|---|---|
| 1 | `generate_demo_data` | `notebook_task` (or Python wheel) | Optional: regenerates the synthetic source feeds (and the demo CDC events) into the volumes. **Disabled in production-like targets**, enabled only in `dev` / demo target. |
| 2 | `run_pipeline` | `pipeline_task` | Triggers the SDP pipeline declared in `resources.pipelines.<key>`. Waits for completion. |
| 3 | `trigger_lakebase_sync` | `notebook_task` (Python) | Calls the Lakebase synced-table API for each of the 3 platinum tables (`creators`, `campaigns`, `brands`) with mode TRIGGERED, waits for each to finish. |
| 4 | `freshness_check` | `notebook_task` (Python) | Reads `MAX(updated_at)` from each Lakebase mirror, compares to `MAX(updated_at)` in the source platinum table. Fails the job if delta > 5 min. |

### Schedule

- **Demo target**: cron every 60s (`* * * * *`) for the live "creator status flip" moment.
- **Production-like target**: cron every 5 minutes — gives the SDP pipeline incremental refresh time, plus headroom for the triggered sync.

### Cluster / compute

All tasks run **serverless** (`environment: serverless`). No JARs, no init scripts.

### `lifecycle.prevent_destroy`

Set on the job AND on Lakebase project (see `03-lakebase-sync.md`) to prevent `bundle destroy` from wiping renewal-week data.

---

## B. The bundle's full resource list

The bundle declares **everything** in `databricks.yml`. The build agent fills in syntax — this is the resource inventory.

| Section | Resource type | What it declares |
|---|---|---|
| `pipelines:` | SDP pipeline | `pulsar_influence_revenue_pipeline` — 4 layers, source files in `src/pipeline/`, serverless |
| `jobs:` | Lakeflow job | `pulsar_influence_revenue_job` (4 tasks above) |
| `postgres_projects:` | Lakebase project | `pulsar-influence` (dedicated) |
| `postgres_endpoints:` | Lakebase compute | autoscale 0.5→4 CU, suspend 300s |
| `apps:` | Databricks App | `pulsar-influence-api` (FastAPI, see `app/*.md`) — with `postgres` and `sql_warehouse` bindings |
| `schemas:` / `volumes:` | UC | The schema is pre-existing; declare the 2 volumes (`raw_data`, `cdc_events`) under `volumes:` |
| `metric_views:` | (declared as SQL files run by a job task — Metric Views aren't yet a first-class DAB resource type) | The 3 metric views from `02-uc-governance.md` |

### What the bundle does NOT declare

- The Postgres **database** (no `postgres_databases` resource type yet — CLI v0.299.1). Created by `app/scripts/lakebase_setup_db.sh`.
- The **GRANT** of `CREATE` + `USAGE` on `public` to the App SP. Done by `app/scripts/lakebase_grant_app_credential.sh` after deploy.
- The `production` Lakebase **branch** — auto-created by the Lakebase CLI on first project creation, no need to declare it.

When the CLI gains `postgres_databases` + a post-deploy hook, fold these two scripts back into `databricks.yml` and delete the wrappers.

---

## C. Variables (per-target overrides)

```yaml
variables:
  catalog:                { default: "ai_demo_gen" }
  schema:                 { default: "demo_influencer_revenue_pipeline_modernized" }
  warehouse_id:           { default: "862f1d757f0424f7" }
  app_name:               { default: "pulsar-influence-api" }
  lakebase_project_id:    { default: "pulsar-influence" }
  lakebase_branch_id:     { default: "production" }
  lakebase_database_name: { default: "dbgen_pulsar_influence" }
  lakebase_database_id:   { default: "db-dbgen-pulsar-influence" }
  triggered_sync_interval: { default: "60s" }     # demo target sets this; prod target sets 5m
```

## D. Targets

```yaml
targets:
  dev:
    mode: development
    default: true
    variables:
      triggered_sync_interval: "60s"
  prod:
    mode: production
    variables:
      triggered_sync_interval: "5m"
```

Per the dab guide, set `mode: production` so Databricks adds run_as / permission protections automatically.

---

## E. Deploy command sequence

```bash
# One-time, before first deploy:
./app/scripts/lakebase_setup_db.sh \
  --db-name dbgen_pulsar_influence \
  --project-id pulsar-influence \
  --database-id db-dbgen-pulsar-influence

# Each deploy:
databricks bundle deploy --target dev

# Once after first deploy:
./app/scripts/lakebase_grant_app_credential.sh \
  --app-name pulsar-influence-api \
  --project-id pulsar-influence \
  --db-name dbgen_pulsar_influence

# Trigger the job manually for the demo:
databricks bundle run pulsar_influence_revenue_job --target dev
```

---

## F. Validation

| Check | Expected |
|---|---|
| `databricks bundle validate --target dev` | OK, no errors |
| `databricks bundle deploy --target dev` | Creates pipeline, job, Lakebase project + endpoint, App. Idempotent on re-run. |
| Job's first run | All 4 tasks succeed. `freshness_check` reports source-vs-Lakebase delta < 5 min. |
| Re-deploy after bumping a SQL file in `src/pipeline/` | Bundle redeploys only the pipeline; Lakebase + App unchanged. |
| `bundle destroy --target dev` | Refuses to wipe the Lakebase project + App because of `lifecycle.prevent_destroy: true`. |

Write `lakeflow_job_id` and `pipeline_id` into `resources.json.created_resources`.
