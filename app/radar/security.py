"""API-key authentication with two scopes.

portfolio: may read every brand (an operator at the platform company).
brand:     may read exactly one account_id; any other id returns 404, never 403, so keys cannot
           be used to probe which brands exist.
"""
from dataclasses import dataclass

from fastapi import Header, HTTPException, Request

from . import store


@dataclass
class Caller:
    label: str
    scope: str
    account_id: str | None

    def can_read(self, account_id: str) -> bool:
        return self.scope == "portfolio" or self.account_id == account_id


def caller(request: Request, x_api_key: str | None = Header(default=None, alias="X-Api-Key")) -> Caller:
    if not x_api_key:
        raise HTTPException(401, "X-Api-Key header is required")
    row = store.one(f"SELECT label, scope, account_id FROM {store.APP_SCHEMA}.api_keys WHERE key_hash = %s AND active",
                    (store.key_hash(x_api_key),))
    if not row:
        raise HTTPException(401, "invalid or inactive API key")
    request.state.caller_label = row["label"]
    return Caller(row["label"], row["scope"], row["account_id"])


def require_portfolio(c: Caller) -> Caller:
    if c.scope != "portfolio":
        raise HTTPException(403, "portfolio-scoped key required")
    return c


def require_brand_access(c: Caller, account_id: str) -> None:
    if not c.can_read(account_id):
        raise HTTPException(404, "brand not found")
