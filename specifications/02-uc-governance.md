# UC Governance — Metric Views

Tables defined in `01-lakeflow.md`. Skill: `databricks-metric-views`.

These metric views give the API and any SQL consumer a single, governed semantic layer over the Platinum streaming tables. The customer-facing API (`app/*.md`) does not strictly *need* them at runtime (it reads Lakebase), but the same KPIs are surfaced through metric views so analysts using SQL get the same numbers as the API. They're also what a future Genie space or BI report would point at.

## Metric View — `mv_creator_roi`

**Source**: `platinum_creator_360`. Aggregated materialization, refresh every 1h.

**Dimensions**: `creator_id`, `tier`, `platform`, `country`, `status`.

**Measures**:

| Name | Expression |
|---|---|
| `attributed_revenue_30d` | `SUM(attributed_revenue_30d_usd)` |
| `engagements_30d` | `SUM(engagements_30d)` |
| `ad_spend_30d` | `SUM(ad_spend_30d_usd)` |
| `roi` | `MEASURE(attributed_revenue_30d) / NULLIF(MEASURE(ad_spend_30d), 0)` |

## Metric View — `mv_campaign_revenue`

**Source**: `platinum_campaign_360`. Aggregated materialization, refresh every 1h.

**Dimensions**: `campaign_id`, `account_id`, `brand_name`, `tier`, `status`.

**Measures**:

| Name | Expression |
|---|---|
| `total_revenue` | `SUM(total_revenue_usd)` |
| `total_spend` | `SUM(total_spend_usd)` |
| `roi` | `MEASURE(total_revenue) / NULLIF(MEASURE(total_spend), 0)` |
| `active_campaigns` | `COUNT(CASE WHEN status='active' THEN 1 END)` |

## Metric View — `mv_renewal_health`

**Source**: `platinum_brand_360`. Aggregated materialization, refresh every 1h.

**Dimensions**: `account_id`, `brand_name`, `tier`, `renewal_status`, `country`.

**Measures**:

| Name | Expression |
|---|---|
| `renewal_arr` | `SUM(renewal_arr_usd)` |
| `ytd_attributed_revenue` | `SUM(ytd_attributed_revenue_usd)` |
| `active_campaign_count` | `SUM(active_campaigns)` |
| `avg_renewal_health_score` | `AVG(renewal_health_score)` |
| `at_risk_arr` | `SUM(CASE WHEN renewal_status='up_for_renewal' AND renewal_health_score < 60 THEN renewal_arr_usd ELSE 0 END)` |

## Validation

| Check | Expected |
|---|---|
| `MEASURE(renewal_arr) WHERE renewal_status='up_for_renewal'` | ≈ $1.2M |
| `MEASURE(roi)` for `mv_creator_roi` filtered to `creator_id='CR-00042'` | Visibly higher in the recent 30d window than baseline |
| `mv_renewal_health` returns the 5 headline accounts (ACC-00001..5) | Yes |
| `DESCRIBE EXTENDED` shows aggregated materialization on each MV | Yes |

Write the metric view names into `resources.json.created_resources.metric_view_name` (use the most representative one — `mv_renewal_health` — or extend the schema to a list if you prefer).
