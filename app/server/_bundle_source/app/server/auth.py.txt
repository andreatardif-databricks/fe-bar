"""
Authentication for the Traackr Influencer Revenue API.

- Brand routes use a per-brand API key in `X-Brand-API-Key`.
  Keys are stored in `public.api_keys` and scoped in one of three ways:
    * brand_scope='all'         — key works for any brand_id
    * brand_scope='brand_name'  — key works for any account_id whose brand_name matches
    * brand_scope='account_id'  — key works only for the exact account_id (legacy)
- Internal `/v1/freshness` requires a Databricks OBO header injected by Apps.
- Admin routes (key management) also require OBO.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional
from fastapi import Header, HTTPException, status
from . import db


def _lookup_key(api_key: str) -> Optional[dict]:
    """Return the key row, or None if not found."""
    return db.fetch_one(
        """
        SELECT api_key, brand_id, brand_scope, label, is_active,
               rate_limit_per_min, expires_at, use_count
        FROM public.api_keys
        WHERE api_key = %s
        """,
        (api_key,),
    )


def _resolve_url_brand(brand_id: str) -> Optional[dict]:
    return db.fetch_one(
        f"SELECT account_id, brand_name, tier, country FROM {db.SYNCED_SCHEMA}.synced_brands WHERE account_id = %s",
        (brand_id,),
    )


def _key_grants_access(key_row: dict, url_brand: dict) -> bool:
    scope = key_row["brand_scope"]
    if scope == "all":
        return True
    if scope == "account_id":
        return key_row["brand_id"] == url_brand["account_id"]
    if scope == "brand_name":
        return key_row["brand_id"] == url_brand["brand_name"]
    return False


def _bump_usage(api_key: str) -> None:
    try:
        with db.get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE public.api_keys SET last_used_at = now(), use_count = use_count + 1 WHERE api_key = %s",
                    (api_key,),
                )
    except Exception:
        pass  # never block a request on telemetry


def require_brand_key(
    brand_id: str,
    x_brand_api_key: Optional[str] = Header(default=None, alias="X-Brand-API-Key"),
) -> dict:
    """Validate the API key and that it grants access to the URL's brand_id."""
    if not x_brand_api_key:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing X-Brand-API-Key header")
    try:
        key_row = _lookup_key(x_brand_api_key)
    except Exception as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, f"Auth backend down: {e}")
    if not key_row:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unknown API key")
    if not key_row["is_active"]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "API key revoked")
    if key_row["expires_at"] is not None and key_row["expires_at"] < datetime.now(timezone.utc):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "API key expired")

    url_brand = _resolve_url_brand(brand_id)
    if not url_brand:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Brand {brand_id} not found")

    if not _key_grants_access(key_row, url_brand):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Key does not grant access to this brand")

    _bump_usage(x_brand_api_key)
    return {
        "brand_id": url_brand["account_id"],
        "brand_name": url_brand["brand_name"],
        "tier": url_brand["tier"],
        "country": url_brand["country"],
        "key_label": key_row["label"],
        "key_scope": key_row["brand_scope"],
    }


def require_obo(
    x_forwarded_access_token: Optional[str] = Header(default=None, alias="X-Forwarded-Access-Token"),
    x_forwarded_user: Optional[str] = Header(default=None, alias="X-Forwarded-User"),
) -> dict:
    if not x_forwarded_access_token and not x_forwarded_user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Internal endpoint requires Databricks user OBO")
    return {"user": x_forwarded_user}


def require_active_key(
    x_brand_api_key: Optional[str] = Header(default=None, alias="X-Brand-API-Key"),
) -> dict:
    """Validate that the X-Brand-API-Key is active and not expired.

    Used for direct-entity lookups (`/v1/creators/{id}`, `/v1/campaigns/{id}`) that
    are not scoped to a brand_id path param. Returns the key row so callers can
    enforce per-entity scope checks (e.g. campaigns: account_id must match the
    key's brand_name).
    """
    if not x_brand_api_key:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing X-Brand-API-Key header")
    try:
        key_row = _lookup_key(x_brand_api_key)
    except Exception as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, f"Auth backend down: {e}")
    if not key_row:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unknown API key")
    if not key_row["is_active"]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "API key revoked")
    if key_row["expires_at"] is not None and key_row["expires_at"] < datetime.now(timezone.utc):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "API key expired")
    _bump_usage(x_brand_api_key)
    return {
        "api_key": x_brand_api_key,
        "key_label": key_row["label"],
        "brand_scope": key_row["brand_scope"],
        "scope_value": key_row["brand_id"],
    }


def reload_brand_keys() -> int:
    try:
        rows = db.fetch_all("SELECT count(*) AS n FROM public.api_keys WHERE is_active")
        return int(rows[0]["n"]) if rows else 0
    except Exception:
        return 0
