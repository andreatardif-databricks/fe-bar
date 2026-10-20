# Deploy — Traackr Influencer Revenue Pipeline

> The bundle resource keys (`pulsar_setup`, `pulsar_orchestration`, `pulsar_app`) and
> the deployed resource names (`pulsar-influence-api`, `pulsar-influence-lb`,
> `dbgen_pulsar_influence`) match the live demo workspace. For a fresh Traackr
> deployment, override these via `--var=app_name=...`, `--var=lakebase_instance_name=...`,
> `--var=lakebase_database_name=...` (see `README.md` for full details).


```bash
# 1. Deploy the bundle (UC schema/volumes, pipeline, jobs, app)
databricks bundle deploy

# 2. One-time setup — provisions Lakebase Database Instance + 3 synced tables + 3 metric views
#    (the first pipeline run is a task inside this job, so platinum tables exist before sync creation)
databricks bundle run pulsar_setup

# 3. Grant the App service principal a Postgres role on the Lakebase database
#    (legacy Database Instance has no `postgres` resource binding type yet, so this is manual)
APP_SP=$(databricks apps get pulsar-influence-api --output json | jq -r '.service_principal_client_id')
databricks workspace-bindings update database/pulsar-influence-lb --bindings catalog/$APP_SP=BINDING_TYPE_BINDING_READ_WRITE
# then connect once as the workspace admin and run:
#   GRANT CONNECT ON DATABASE dbgen_pulsar_influence TO "<sp-uuid>";
#   GRANT USAGE, CREATE ON SCHEMA public TO "<sp-uuid>";

# 4. Start the app
databricks bundle run pulsar_app

# 5. (Day-2) Refresh data + pipeline + sync + freshness SLA check
databricks bundle run pulsar_orchestration
```

## Notes

- **SDP volume paths are hardcoded** in `src/pipeline/01_bronze.sql` to `ai_demo_gen.demo_influencer_revenue_pipeline_modernized` — override `--var="catalog=…"` / `--var="schema=…"` only if you also edit those paths.
- **Lakebase is NOT bundle-declarable**: synced tables require a *legacy* Database Instance (the autoscale Postgres project type doesn't support reverse-ETL yet), and there's no DAB resource type for either. `src/deploy/setup_lakebase.py` and `create_synced_tables.py` create them via SDK, idempotently.
- **App `postgres` binding is omitted** for the same reason. The app reads `PG_INSTANCE_NAME` from `app.yaml` and resolves PGHOST/PGUSER + a fresh OAuth token via the SDK at startup using the SP identity.
- **Day-2 schedule**: attach a cron trigger to `pulsar_orchestration` in `databricks.yml` if you want it to run unattended.

## Teardown

```bash
databricks bundle destroy --auto-approve
# Lakebase Database Instance, synced tables, and the App are NOT destroyed
# (the App has prevent_destroy; the Lakebase instance is not bundle-managed).
# Drop them manually if needed:
#   databricks database delete-database-instance pulsar-influence-lb
#   databricks apps delete pulsar-influence-api
```
