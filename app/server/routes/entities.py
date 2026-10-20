"""Direct entity lookups: GET /v1/creators/{id} and /v1/campaigns/{id}.

These exist alongside the brand-scoped list routes in brands.py so callers can
verify a single entity (useful for the Live Change Propagation tab, which only
changes one row at a time). Auth is X-Brand-API-Key validated as active (not
scoped to a brand_id path param, since the URL does not carry one).

For campaigns, we additionally enforce the key's brand_scope against the
campaign's account_id so a brand-scoped key cannot read a competitor's
campaign. Creators are not strictly brand-scoped in this demo (the data model
shares Maya's roster across all brands), so we allow any active key to look
up any creator.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from .. import db
from ..auth import require_active_key

router = APIRouter(tags=["entities"])


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.get("/v1/creators/{creator_id}")
def get_creator(creator_id: str, key=Depends(require_active_key)):
    row = db.fetch_one(
        f"""
        SELECT creator_id, handle, display_name, tier, platform, country,
               status, follower_count, agent_email, updated_at
        FROM {db.SYNCED_SCHEMA}.synced_creators
        WHERE creator_id = %s
        """,
        (creator_id,),
    )
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"creator {creator_id} not found")
    return {
        "creator_id": row["creator_id"],
        "handle": row["handle"],
        "display_name": row["display_name"],
        "tier": row["tier"],
        "platform": row["platform"],
        "country": row["country"],
        "status": row["status"],
        "follower_count": int(row["follower_count"] or 0),
        "agent_email": row["agent_email"],
        "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
        "as_of": _now_iso(),
    }


@router.get("/v1/campaigns/{campaign_id}")
def get_campaign(campaign_id: str, key=Depends(require_active_key)):
    row = db.fetch_one(
        f"""
        SELECT c.campaign_id, c.account_id, c.name, c.start_date, c.end_date,
               c.budget_usd, c.status, c.created_at, c.updated_at,
               b.brand_name
        FROM {db.SYNCED_SCHEMA}.synced_campaigns c
        LEFT JOIN {db.SYNCED_SCHEMA}.synced_brands b ON b.account_id = c.account_id
        WHERE c.campaign_id = %s
        """,
        (campaign_id,),
    )
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"campaign {campaign_id} not found")

    # Enforce brand scope on the campaign's account
    scope = key["brand_scope"]
    scope_value = key["scope_value"]
    if scope == "account_id" and scope_value != row["account_id"]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "API key does not grant access to this campaign's brand")
    if scope == "brand_name" and scope_value != row["brand_name"]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "API key does not grant access to this campaign's brand")

    return {
        "campaign_id": row["campaign_id"],
        "account_id": row["account_id"],
        "brand_name": row["brand_name"],
        "name": row["name"],
        "start_date": row["start_date"].isoformat() if row["start_date"] else None,
        "end_date": row["end_date"].isoformat() if row["end_date"] else None,
        "budget_usd": float(row["budget_usd"] or 0),
        "status": row["status"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
        "as_of": _now_iso(),
    }
