# Orchestration Execution Evidence

Workspace: `dbc-01f27b97-0e2e.cloud.databricks.com`  
Job: `[prod] Pulsar — Daily Orchestration` (`357780382169889`)

## Verified task executions

The following real run IDs were captured while completing the integrated build:

| Stage | Run ID | Result |
|---|---:|---|
| Synthetic data generation | `604414364013544` | `TERMINATED / SUCCESS` |
| Lakeflow SDP pipeline | `315615457395512` | `TERMINATED / SUCCESS` |
| Persisted GenAI generation | `412595958307978` | `TERMINATED / SUCCESS` |
| Lakebase triggered sync | `853197966200363` | `TERMINATED / SUCCESS` |
| Freshness validation | parent run `294121103304327` | `TERMINATED / SUCCESS` |

## Final clean integrated run

Parent run: `969307369960771` — `TERMINATED / SUCCESS`

| Task | Run ID | Duration | Result |
|---|---:|---:|---|
| `generate_demo_data` | `893211176158689` | 107 s | `SUCCESS` |
| `run_pipeline` | `80910690997596` | 202 s | `SUCCESS` |
| `generate_ai_insights` | `1007858851997711` | 305 s | `SUCCESS` |
| `trigger_lakebase_sync` | `822297336579864` | 57 s | `SUCCESS` |
| `freshness_check` | `93846752616110` | 23 s | `SUCCESS` |

The deployed dependency graph is:

```text
generate_demo_data
  → run_pipeline
      → generate_ai_insights
          → trigger_lakebase_sync
              → freshness_check
```

During implementation, the first sync attempt exposed a missing SDK dependency and the first freshness attempt exposed starter-era Lakebase names. Both root causes were corrected in `databricks.yml` and `src/jobs/freshness_check.py`; the targeted reruns above then succeeded.
