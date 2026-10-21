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


@router.get("/portfolio/summary", operation_id="getPortfolioSummary", summary="Headline numbers computed live from Lakebase")
def portfolio_summary(caller: Caller = Depends(security.caller)):
    security.require_portfolio(caller)
    risk = store.rows(f'''SELECT risk_band, COUNT(*) AS brands, ROUND(SUM(arr_usd)::numeric, 0) AS arr_usd
                          FROM "{S}".synced_brand_radar GROUP BY risk_band ORDER BY risk_band''')
    opp = store.one(f'''SELECT COUNT(*) AS campaigns, ROUND(SUM(incremental_revenue_usd)::numeric, 0) AS incremental_revenue_usd,
                        ROUND(SUM(spend_90d_usd)::numeric, 0) AS spend_90d_usd FROM "{S}".synced_campaign_actions''')
    roi = store.rows(f'''SELECT region, ROUND((SUM(revenue_usd) / NULLIF(SUM(spend_usd), 0))::numeric, 2) AS roi
                         FROM "{S}".synced_campaign_roi GROUP BY region ORDER BY region''')
    return {"risk_by_band": [_clean(r) for r in risk], "top_actions": _clean(opp or {}), "roi_by_region": [_clean(r) for r in roi]}


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
