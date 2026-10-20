# Customer-Facing API — Endpoints

All endpoints are read-only. They query Lakebase (`public.creators`, `public.campaigns`, `public.brands`) created by the triggered synced tables in `03-lakebase-sync.md`. SQL is plain `SELECT` — no joins to Delta, no warehouse round-trips for hot paths.

p95 latency target: < 100 ms.

## Brand-client endpoints (require `X-Brand-API-Key` matching path `brand_id`)

### `GET /v1/brands/{brand_id}/creators`

Returns the brand's creator roster with current ROI.

**Query params**: `status` (optional, default `active`), `limit` (default 50, max 200).

**Response shape**:

```json
{
  "brand_id": "ACC-00001",
  "brand_name": "Coach",
  "as_of": "2026-05-27T19:42:31Z",
  "creators": [
    {
      "creator_id": "CR-00042",
      "handle": "@sofia.styles",
      "tier": "macro",
      "platform": "tiktok",
      "status": "active",
      "follower_count": 2400000,
      "attributed_revenue_30d_usd": 124000,
      "engagements_30d": 4280000,
      "ad_spend_30d_usd": 38000,
      "roi": 3.26,
      "updated_at": "2026-05-27T19:39:14Z"
    }
  ]
}
```

**SQL** (functional):

```sql
SELECT c.*
FROM public.creators c
JOIN public.campaigns ca ON ca.account_id = $1
                        AND ca.status IN ('active','paused')
WHERE c.creator_id IN (SELECT DISTINCT creator_id FROM ... attributed to ca)
  AND ($2::text IS NULL OR c.status = $2)
ORDER BY c.attributed_revenue_30d_usd DESC
LIMIT $3;
```

> The "creators attributed to this brand's campaigns" join uses a `campaign_creators` lookup that the synced-table writer derives from Platinum. If the build agent finds this complex, simpler shortcut: persist `account_id` directly on `public.creators` (Platinum-side) for the demo. The story doesn't suffer.

### `GET /v1/brands/{brand_id}/campaigns`

Returns the brand's active and recent campaigns with revenue + ROI.

**Query params**: `status` (optional: `active|ended|all`, default `active`), `limit` (default 50).

**Response shape**:

```json
{
  "brand_id": "ACC-00001",
  "brand_name": "Coach",
  "as_of": "2026-05-27T19:42:31Z",
  "campaigns": [
    {
      "campaign_id": "CMP-01337",
      "name": "Spring Capsule",
      "start_date": "2026-03-15",
      "end_date": "2026-06-10",
      "budget_usd": 250000,
      "total_spend_usd": 184000,
      "total_revenue_usd": 612000,
      "roi": 3.32,
      "status": "active",
      "updated_at": "2026-05-27T19:39:14Z"
    }
  ]
}
```

### `GET /v1/brands/{brand_id}/renewal-health`

The renewal indicator brand-client portals show on their account dashboard.

**Response shape**:

```json
{
  "brand_id": "ACC-00001",
  "brand_name": "Coach",
  "tier": "enterprise",
  "renewal_status": "up_for_renewal",
  "renewal_date": "2026-06-15",
  "renewal_arr_usd": 400000,
  "ytd_attributed_revenue_usd": 2840000,
  "active_campaigns": 3,
  "renewal_health_score": 78,
  "updated_at": "2026-05-27T19:39:14Z"
}
```

`renewal_health_score` comes straight from `public.brands.renewal_health_score`.

## Internal endpoint (Databricks OBO — not brand-key)

### `GET /v1/freshness`

End-to-end freshness inspector. The demo's "proof" tile during Act 4.

**Response shape**:

```json
{
  "checked_at": "2026-05-27T19:42:31Z",
  "tables": [
    {
      "name": "creators",
      "source_max_updated_at": "2026-05-27T19:39:09Z",
      "lakebase_max_updated_at": "2026-05-27T19:39:14Z",
      "lakebase_max_synced_at": "2026-05-27T19:40:02Z",
      "lag_seconds": 53
    },
    { "name": "campaigns", "...": "..." },
    { "name": "brands",    "...": "..." }
  ]
}
```

`source_max_updated_at` comes from the SQL Warehouse (`SELECT MAX(updated_at) FROM platinum_<x>`); `lakebase_max_*` come from Postgres. The endpoint runs both queries concurrently. This is the only endpoint that hits the warehouse.

## Demo `curl` script

`app/scripts/demo_curl.sh` runs Act 4 in 6 calls (saved env vars: `$API`, `$KEY`, `$BRAND_ID=ACC-00001`):

```bash
curl -s -H "X-Brand-API-Key: $KEY" $API/v1/brands/$BRAND_ID/renewal-health | jq
curl -s -H "X-Brand-API-Key: $KEY" $API/v1/brands/$BRAND_ID/creators | jq '.creators[] | select(.creator_id=="CR-00042")'
# (run the 'flip CR-00042 to paused' SQL into the cdc events folder here)
sleep 90  # wait for the orchestration job to roll the change through
curl -s -H "X-Brand-API-Key: $KEY" $API/v1/brands/$BRAND_ID/creators | jq '.creators[] | select(.creator_id=="CR-00042")'   # status now 'paused'
curl -s $API/v1/freshness | jq    # all 3 tables show lag < 90s
```

## Validation

| Check | Expected |
|---|---|
| `GET /v1/brands/ACC-00001/renewal-health` (Coach) | 200, `renewal_arr_usd: 400000` |
| `GET /v1/brands/ACC-00001/creators` returns CR-00042 | Yes, with non-zero `attributed_revenue_30d_usd` (recent surge) |
| Same with `X-Brand-API-Key: pk_demo_loreal` against ACC-00001 | 403 — key/brand mismatch |
| No key | 401 |
| `GET /v1/freshness` without Databricks OBO | 401 |
| After flipping CR-00042 to `paused` and waiting 2 min | `creators` endpoint returns `status: "paused"` for CR-00042 |
| p95 latency for `/creators` and `/renewal-health` (load test, 50 RPS) | < 100 ms |
