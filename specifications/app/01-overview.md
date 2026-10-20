# Customer-Facing API — Overview

This is **not** the React/AppKit operational app from the demo-skill template. It's a slim **FastAPI service** deployed on Databricks Apps, exposing public REST endpoints that brand clients (Coach, L'Oréal, Adidas, ...) call from their own portals. There is no UI, no chat dock, no agent, no operations queue — those live in the React template and are out of scope.

The service reads from **Lakebase** (Postgres synced from Platinum — see `03-lakebase-sync.md`). It does not query the lakehouse warehouse for hot endpoints; sub-100 ms p95 is the target.

## Persona alignment

- **Maya Patel** (the demo's hero) ships and operates this API. She's not a brand-client user.
- **Brand-client users** are downstream of this demo — they don't appear in the demo itself; they're represented by `curl` calls Maya runs from a side terminal during Act 4.
- **Maya's "wow" moment** is the live update: she changes one creator's status in the source, watches it propagate end-to-end, and proves it on the API in <3 minutes.

## Skill to use

`databricks-apps-python` — read `SKILLS/databricks-apps-python/SKILL.md` for the FastAPI-on-Databricks-Apps pattern (Python framework fallback, since this is API-only with no UI). The AppKit template is **not used** — Maya's API has no React surface.

## What ships

- A single FastAPI Python app under `app/` in the project repo.
- `app.yaml` declaring the entrypoint and the `LAKEBASE_ENDPOINT` env var sourced from the `postgres` binding.
- The two Lakebase scripts (`lakebase_setup_db.sh`, `lakebase_grant_app_credential.sh`) under `app/scripts/` — these are the same two scripts referenced from the bundle in `04-orchestration-dab.md`.
- A `curl` demo script (`app/scripts/demo_curl.sh`) that hits the brand-client endpoints in order — used for Act 4 of the walkthrough.

## File layout

```
app/
├── app.yaml                              # Databricks App descriptor (command, env, port)
├── pyproject.toml                        # FastAPI, asyncpg, uvicorn, databricks-sdk
├── server/
│   ├── main.py                           # FastAPI app + router include
│   ├── db.py                             # asyncpg pool, builds DSN from PG* env vars
│   ├── auth.py                           # Databricks OBO + simple per-brand API key check
│   └── routes/
│       ├── brands.py                     # /v1/brands/* endpoints
│       └── freshness.py                  # /v1/freshness — internal observability
└── scripts/
    ├── lakebase_setup_db.sh
    ├── lakebase_grant_app_credential.sh
    └── demo_curl.sh
```

## Authentication model (what to implement; deliberately simple)

- **Brand-client requests**: HTTP header `X-Brand-API-Key`. The key is a deterministic string generated per `account_id` for the demo (e.g. `pk_demo_<lowercase brand_name>` — `pk_demo_coach`, `pk_demo_loreal`, etc.). The route resolves the key → `account_id`, then enforces that the path's `{brand_id}` matches.
- **Internal `/v1/freshness`**: requires Databricks OBO (the user's identity). Brand keys do NOT grant access to this route.

Both checks live in `server/auth.py`. The build agent should not over-engineer auth — this is a demo, the brand-key resolution is a small dict seeded at startup from the `brands` table.

## Bundle binding (declared in `04-orchestration-dab.md`)

```yaml
apps:
  pulsar_api:
    name: ${var.app_name}
    description: "Pulsar Influence — customer-facing brand-client API"
    source_code_path: ./app
    resources:
      - name: postgres
        postgres:
          branch: projects/${var.lakebase_project_id}/branches/${var.lakebase_branch_id}
          database: projects/${var.lakebase_project_id}/branches/${var.lakebase_branch_id}/databases/${var.lakebase_database_id}
          permission: CAN_CONNECT_AND_CREATE
      - name: sql-warehouse
        sql_warehouse:
          id: ${var.warehouse_id}
          permission: CAN_USE
```

## `app.yaml` (functional shape)

```yaml
command: ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"]
env:
  - name: LAKEBASE_ENDPOINT
    valueFrom: postgres
  - name: PULSAR_BRAND_KEY_PREFIX
    value: "pk_demo_"
```

The platform auto-injects `PGHOST` / `PGDATABASE` / `PGSSLMODE` / `PGUSER` / `PGPORT` / `PGAPPNAME` from the `postgres` binding. `server/db.py` reads them directly.

## What this app is NOT doing

- No UI. No HTML, no React, no AppKit.
- No agent, no chat, no MAS / KA / Genie — none of those capabilities are in this demo.
- No mutations of brand data. **All endpoints are read-only.**
- No long-lived background workers. The triggered Lakebase sync happens in the orchestration job (see `04-orchestration-dab.md`), not in this app.
