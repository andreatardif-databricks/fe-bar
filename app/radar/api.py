"""Versioned read API served entirely from Lakebase."""
import os
import time

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from . import security, store
from .security import Caller

router = APIRouter(prefix="/v1")
S = store.SYNCED_SCHEMA


class RenewalHealth(BaseModel):
    account_id: str
    brand_name: str
    region: str
    tier: str
    arr_usd: float
    renewal_date: str | None
    renewal_risk_score: float
    risk_band: str
    avg_roi_180d: float
    active_campaigns: int
    revenue_trend_90d: float
    late_invoice_rate: float
    scored_at: str | None
    model_uri: str | None


class CampaignKpi(BaseModel):
    campaign_id: str
    campaign_name: str
    status: str | None
    region: str
    spend_usd: float | None
    revenue_usd: float | None
    roi: float | None
    roi_90d: float | None
    budget_usd: float | None


class Recommendation(BaseModel):
    campaign_id: str
    campaign_name: str
    spend_90d_usd: float
    roi_90d: float
    benchmark_roi: float
    incremental_revenue_usd: float
    risk_band: str
    renewal_risk_score: float
    recommendation: str
    generated_at: str | None


def _clean(row: dict) -> dict:
    return {k: (v.isoformat() if hasattr(v, "isoformat") else (float(v) if hasattr(v, "as_tuple") else v)) for k, v in row.items()}


@router.get("/brands/{account_id}/renewal-health", response_model=RenewalHealth, operation_id="getRenewalHealth",
            summary="Modelled renewal risk and the features behind it")
def renewal_health(account_id: str, caller: Caller = Depends(security.caller)):
    security.require_brand_access(caller, account_id)
    row = store.one(f'SELECT * FROM "{S}".synced_brand_radar WHERE account_id = %s', (account_id,))
    if not row:
        raise HTTPException(404, "brand not found")
    return _clean(row)


@router.get("/brands/{account_id}/campaigns", response_model=list[CampaignKpi], operation_id="listBrandCampaigns",
            summary="Campaign ROI for one brand")
def brand_campaigns(account_id: str, status: str | None = None, limit: int = Query(50, le=200),
                    caller: Caller = Depends(security.caller)):
    security.require_brand_access(caller, account_id)
    sql = f"""SELECT k.campaign_id, k.campaign_name, k.status, k.region, k.spend_usd, k.revenue_usd, k.roi, k.roi_90d, c.budget_usd
              FROM "{S}".synced_campaign_roi k LEFT JOIN "{S}".synced_campaigns c USING (campaign_id)
              WHERE k.account_id = %s"""
    params: list = [account_id]
    if status:
        sql += " AND k.status = %s"
        params.append(status)
    sql += " ORDER BY k.spend_usd DESC NULLS LAST LIMIT %s"
    params.append(limit)
    return [_clean(r) for r in store.rows(sql, tuple(params))]


@router.get("/brands/{account_id}/recommendations", response_model=list[Recommendation], operation_id="listBrandRecommendations",
            summary="Persisted ai_gen actions for a brand's underperforming campaigns")
def brand_recommendations(account_id: str, caller: Caller = Depends(security.caller)):
    security.require_brand_access(caller, account_id)
    return [_clean(r) for r in store.rows(
        f'SELECT * FROM "{S}".synced_campaign_actions WHERE account_id = %s ORDER BY incremental_revenue_usd DESC', (account_id,))]


@router.get("/portfolio/risk", operation_id="listPortfolioRisk", summary="Brands ranked by modelled renewal risk")
def portfolio_risk(limit: int = Query(25, le=200), band: str | None = None, caller: Caller = Depends(security.caller)):
    security.require_portfolio(caller)
    sql = f'SELECT account_id, brand_name, region, tier, arr_usd, renewal_date, renewal_risk_score, risk_band FROM "{S}".synced_brand_radar'
    params: list = []
    if band:
        sql += " WHERE risk_band = %s"
        params.append(band)
    sql += " ORDER BY renewal_risk_score DESC LIMIT %s"
    params.append(limit)
    return [_clean(r) for r in store.rows(sql, tuple(params))]


@router.get("/portfolio/actions", response_model=list[Recommendation], operation_id="listPortfolioActions",
            summary="Largest persisted ai_gen actions across all brands")
def portfolio_actions(limit: int = Query(25, le=100), caller: Caller = Depends(security.caller)):
    security.require_portfolio(caller)
    return [_clean(r) for r in store.rows(
        f'SELECT * FROM "{S}".synced_campaign_actions ORDER BY incremental_revenue_usd DESC LIMIT %s', (limit,))]


@router.get("/portfolio/summary", operation_id="getPortfolioSummary", summary="Portfolio headline numbers computed live from Lakebase")
def portfolio_summary(caller: Caller = Depends(security.caller)):
    security.require_portfolio(caller)
    risk = store.rows(f'''SELECT risk_band, COUNT(*)::int AS brands, ROUND(SUM(arr_usd)::numeric, 0) AS arr_usd
                          FROM "{S}".synced_brand_radar GROUP BY risk_band ORDER BY risk_band''')
    opp = store.one(f'''SELECT COUNT(*)::int AS campaigns, ROUND(SUM(incremental_revenue_usd)::numeric, 0) AS incremental_revenue_usd,
                        ROUND(SUM(spend_90d_usd)::numeric, 0) AS spend_90d_usd FROM "{S}".synced_campaign_actions''')
    roi = store.rows(f'''SELECT region, ROUND((SUM(revenue_usd) / NULLIF(SUM(spend_usd), 0))::numeric, 2) AS roi
                         FROM "{S}".synced_campaign_roi GROUP BY region ORDER BY region''')
    book = store.one(f'''SELECT COUNT(*)::int AS brands, SUM(arr_usd)::float AS arr_usd, AVG(renewal_risk_score)::float AS avg_churn,
                         SUM(renewal_risk_score * arr_usd)::float AS expected_loss_usd,
                         COUNT(*) FILTER (WHERE renewal_date <= current_date + 90)::int AS renewing_90d,
                         COALESCE(SUM(arr_usd) FILTER (WHERE renewal_date <= current_date + 90), 0)::float AS renewing_90d_arr,
                         COUNT(*) FILTER (WHERE renewal_date <= current_date + 90 AND risk_band = 'high')::int AS high_risk_renewing_90d,
                         COALESCE(SUM(arr_usd) FILTER (WHERE renewal_date <= current_date + 90 AND risk_band = 'high'), 0)::float AS high_risk_renewing_90d_arr
                         FROM "{S}".synced_brand_radar''')
    spend = store.one(f'''SELECT COUNT(*)::int AS campaigns, COUNT(*) FILTER (WHERE status = 'active')::int AS active,
                         SUM(spend_usd)::float AS spend_usd, SUM(revenue_usd)::float AS revenue_usd,
                         (SUM(revenue_usd) / NULLIF(SUM(spend_usd), 0))::float AS roi,
                         COUNT(*) FILTER (WHERE roi_90d < 1)::int AS below_breakeven FROM "{S}".synced_campaign_roi''')
    by_region = store.rows(f'''SELECT region, COUNT(*)::int AS brands, ROUND(SUM(arr_usd)::numeric, 0) AS arr_usd,
                           ROUND((AVG(renewal_risk_score) * 100)::numeric, 0) AS avg_churn_pct,
                           COUNT(*) FILTER (WHERE risk_band = 'high')::int AS high_risk
                           FROM "{S}".synced_brand_radar GROUP BY region ORDER BY region''')
    top = store.rows(f'''SELECT account_id, brand_name, region, tier, arr_usd, renewal_date, renewal_risk_score,
                        (renewal_risk_score * arr_usd) AS expected_loss_usd FROM "{S}".synced_brand_radar
                        ORDER BY renewal_risk_score * arr_usd DESC LIMIT 5''')
    asked = store.one(f"SELECT COUNT(*)::int AS n FROM {store.APP_SCHEMA}.request_log WHERE route = '/v1/genie/ask'")
    return {"risk_by_band": [_clean(r) for r in risk], "top_actions": _clean(opp or {}), "roi_by_region": [_clean(r) for r in roi],
            "book": _clean(book or {}), "spend": _clean(spend or {}), "by_region": [_clean(r) for r in by_region],
            "top_at_risk": [_clean(r) for r in top], "genie_questions": asked["n"] if asked else 0}


@router.get("/brands/{account_id}/overview", operation_id="getBrandOverview", summary="Everything the brand overview page shows")
def brand_overview(account_id: str, caller: Caller = Depends(security.caller)):
    security.require_brand_access(caller, account_id)
    b = store.one(f'SELECT *, (renewal_date - current_date) AS days_to_renewal FROM "{S}".synced_brand_radar WHERE account_id = %s', (account_id,))
    if not b:
        raise HTTPException(404, "brand not found")
    c = store.one(f'''SELECT COUNT(*)::int AS campaigns, COUNT(*) FILTER (WHERE status = 'active')::int AS active,
                      COUNT(*) FILTER (WHERE status = 'ended')::int AS ended,
                      COALESCE(SUM(spend_usd), 0)::float AS spend_usd, COALESCE(SUM(revenue_usd), 0)::float AS revenue_usd,
                      (SUM(revenue_usd) / NULLIF(SUM(spend_usd), 0))::float AS roi,
                      COUNT(*) FILTER (WHERE roi_90d < 1)::int AS below_breakeven
                      FROM "{S}".synced_campaign_roi WHERE account_id = %s''', (account_id,))
    peers = store.one(f'''SELECT (SUM(revenue_usd) / NULLIF(SUM(spend_usd), 0))::float AS region_roi FROM "{S}".synced_campaign_roi WHERE region = %s''', (b["region"],))
    risk_peers = store.one(f'''SELECT AVG(renewal_risk_score) FILTER (WHERE region = %s)::float AS region_churn,
                             AVG(renewal_risk_score) FILTER (WHERE tier = %s)::float AS tier_churn,
                             AVG(renewal_risk_score)::float AS portfolio_churn FROM "{S}".synced_brand_radar''', (b["region"], b["tier"]))
    rank = store.one(f'''WITH per AS (SELECT account_id, SUM(revenue_usd) / NULLIF(SUM(spend_usd), 0) AS roi FROM "{S}".synced_campaign_roi GROUP BY account_id)
                      SELECT (COUNT(*) FILTER (WHERE roi > (SELECT roi FROM per WHERE account_id = %s)) + 1)::int AS rank, COUNT(*)::int AS brands FROM per''', (account_id,))
    best = store.one(f'SELECT campaign_name, roi::float, spend_usd::float FROM "{S}".synced_campaign_roi WHERE account_id = %s AND spend_usd > 1000 ORDER BY roi DESC LIMIT 1', (account_id,))
    worst = store.one(f'SELECT campaign_name, roi::float, spend_usd::float FROM "{S}".synced_campaign_roi WHERE account_id = %s AND spend_usd > 1000 ORDER BY roi ASC LIMIT 1', (account_id,))
    acts = store.one(f'SELECT COUNT(*)::int AS flagged, COALESCE(SUM(incremental_revenue_usd), 0)::float AS opportunity_usd, COALESCE(SUM(spend_90d_usd), 0)::float AS spend_90d_usd FROM "{S}".synced_campaign_actions WHERE account_id = %s', (account_id,))
    asked = store.one(f"SELECT COUNT(*)::int AS n FROM {store.APP_SCHEMA}.request_log WHERE route = '/v1/genie/ask' AND detail->>'account_id' = %s", (account_id,))
    return {"brand": _clean(b), "campaigns": _clean(c or {}), "region_roi": (peers or {}).get("region_roi"), "risk_peers": _clean(risk_peers or {}),
            "roi_rank": _clean(rank or {}), "best_campaign": _clean(best or {}), "worst_campaign": _clean(worst or {}),
            "actions": _clean(acts or {}), "genie_questions": asked["n"] if asked else 0}


@router.get("/creators", operation_id="listCreators", summary="Creator roster, filterable by tier and region")
def creators(tier: str | None = None, region: str | None = None, limit: int = Query(50, le=500), caller: Caller = Depends(security.caller)):
    sql, params = f'SELECT creator_id, handle, tier, platform, region, follower_count, status FROM "{S}".synced_creators WHERE true', []
    if tier:
        sql += " AND tier = %s"
        params.append(tier)
    if region:
        sql += " AND region = %s"
        params.append(region)
    sql += " ORDER BY follower_count DESC LIMIT %s"
    params.append(limit)
    return store.rows(sql, tuple(params))


@router.get("/health", operation_id="health", summary="Liveness and Lakebase round-trip time")
def health():
    t0 = time.perf_counter()
    n = store.one(f'SELECT COUNT(*) AS n FROM "{S}".synced_brand_radar')["n"]
    return {"status": "ok", "brands_served": n, "lakebase_round_trip_ms": round((time.perf_counter() - t0) * 1000, 1),
            "serving_endpoint": os.environ.get("SERVING_ENDPOINT")}
