"""Brand-client read-only endpoints."""
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from .. import db
from ..auth import require_brand_key

router = APIRouter(prefix="/v1/brands", tags=["brands"])


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.get("/{brand_id}/renewal-health")
def renewal_health(brand_id: str, brand=Depends(require_brand_key)):
    row = db.fetch_one(
        f"""
        SELECT account_id, brand_name, tier, country, renewal_status,
               renewal_date, renewal_arr_usd, ytd_attributed_revenue_usd,
               active_campaigns, renewal_health_score, updated_at
        FROM {db.SYNCED_SCHEMA}.synced_brands
        WHERE account_id = %s
        """,
        (brand_id,),
    )
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Brand not found in mirrored Lakebase")
    return {
        "brand_id": row["account_id"],
        "brand_name": row["brand_name"],
        "tier": row["tier"],
        "country": row["country"],
        "renewal_status": row["renewal_status"],
        "renewal_date": row["renewal_date"].isoformat() if row["renewal_date"] else None,
        "renewal_arr_usd": float(row["renewal_arr_usd"] or 0),
        "ytd_attributed_revenue_usd": float(row["ytd_attributed_revenue_usd"] or 0),
        "active_campaigns": int(row["active_campaigns"] or 0),
        "renewal_health_score": int(row["renewal_health_score"] or 0),
        "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
        "as_of": _now_iso(),
    }


@router.get("/{brand_id}/campaigns")
def campaigns(
    brand_id: str,
    status_filter: str = Query(default="active", alias="status"),
    limit: int = Query(default=50, le=200),
    brand=Depends(require_brand_key),
):
    where = "account_id = %s"
    params: tuple = (brand_id,)
    if status_filter and status_filter != "all":
        where += " AND status = %s"
        params = (brand_id, status_filter)
    rows = db.fetch_all(
        f"""
        SELECT campaign_id, account_id, name, start_date, end_date,
               budget_usd, status, updated_at
        FROM {db.SYNCED_SCHEMA}.synced_campaigns
        WHERE {where}
        ORDER BY end_date DESC NULLS LAST
        LIMIT %s
        """,
        params + (limit,),
    )
    return {
        "brand_id": brand_id,
        "brand_name": brand.get("brand_name"),
        "as_of": _now_iso(),
        "campaigns": [
            {
                "campaign_id": r["campaign_id"],
                "name": r["name"],
                "start_date": r["start_date"].isoformat() if r["start_date"] else None,
                "end_date": r["end_date"].isoformat() if r["end_date"] else None,
                "budget_usd": float(r["budget_usd"] or 0),
                "status": r["status"],
                "updated_at": r["updated_at"].isoformat() if r["updated_at"] else None,
            }
            for r in rows
        ],
    }


@router.get("/{brand_id}/creators")
def creators(
    brand_id: str,
    status_filter: str = Query(default="active", alias="status"),
    limit: int = Query(default=50, le=200),
    brand=Depends(require_brand_key),
):
    """
    Demo simplification: return creators handled by a single account-exec email
    (configured below). For the seeded data, this maps to the demo brand's roster
    of ~6 creators so the Try-it panel always returns rows regardless of brand.
    """
    status_param = status_filter if status_filter != "all" else None
    rows = db.fetch_all(
        f"""
        SELECT c.creator_id, c.handle, c.display_name, c.tier, c.platform,
               c.country, c.follower_count, c.status, c.agent_email, c.updated_at
        FROM {db.SYNCED_SCHEMA}.synced_creators c
        WHERE c.agent_email = 'maya.patel@pulsar.com'
          AND (%s::text IS NULL OR c.status = %s)
        ORDER BY c.follower_count DESC NULLS LAST
        LIMIT %s
        """,
        (status_param, status_param, limit),
    )
    return {
        "brand_id": brand_id,
        "brand_name": brand.get("brand_name"),
        "as_of": _now_iso(),
        "creators": [
            {
                "creator_id": r["creator_id"],
                "handle": r["handle"],
                "display_name": r["display_name"],
                "tier": r["tier"],
                "platform": r["platform"],
                "country": r["country"],
                "status": r["status"],
                "follower_count": int(r["follower_count"] or 0),
                "updated_at": r["updated_at"].isoformat() if r["updated_at"] else None,
            }
            for r in rows
        ],
    }
