"""Lakebase access: an OAuth-refreshing connection pool plus the app's own operational tables.

The platform injects PGHOST/PGUSER/PGDATABASE for the bound Lakebase resource. The password is a
short-lived OAuth token, so the pool is rebuilt before the token expires.
"""
import hashlib
import os
import threading
import time

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from databricks.sdk import WorkspaceClient

SYNCED_SCHEMA = os.environ.get("RADAR_SCHEMA", "renewal_radar")
APP_SCHEMA = "radar_app"
ENDPOINT = os.environ.get("LAKEBASE_ENDPOINT", "")
_REFRESH_AFTER_S = 40 * 60

_lock = threading.Lock()
_pool: ConnectionPool | None = None
_built_at = 0.0
_ws = WorkspaceClient()


def _conninfo() -> str:
    token = _ws.postgres.generate_database_credential(endpoint=ENDPOINT).token
    return (f"host={os.environ['PGHOST']} port={os.environ.get('PGPORT', '5432')} dbname={os.environ['PGDATABASE']} "
            f"user={os.environ['PGUSER']} password={token} sslmode=require application_name=renewal-radar")


def pool() -> ConnectionPool:
    global _pool, _built_at
    if _pool is None or time.time() - _built_at > _REFRESH_AFTER_S:
        with _lock:
            if _pool is None or time.time() - _built_at > _REFRESH_AFTER_S:
                old = _pool
                _pool = ConnectionPool(_conninfo(), min_size=1, max_size=6, timeout=15, open=True)
                _built_at = time.time()
                if old:
                    old.close()
    return _pool


def rows(sql: str, params: tuple = ()) -> list[dict]:
    with pool().connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def one(sql: str, params: tuple = ()) -> dict | None:
    result = rows(sql, params)
    return result[0] if result else None


def execute(sql: str, params: tuple = ()) -> None:
    with pool().connection() as conn, conn.cursor() as cur:
        cur.execute(sql, params)


def key_hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def bootstrap() -> None:
    """Create the app-owned tables and seed the demo keys. Idempotent."""
    execute(f"CREATE SCHEMA IF NOT EXISTS {APP_SCHEMA}")
    execute(f"""CREATE TABLE IF NOT EXISTS {APP_SCHEMA}.api_keys (
        key_hash text PRIMARY KEY, label text NOT NULL,
        scope text NOT NULL CHECK (scope IN ('portfolio', 'brand')), account_id text,
        active boolean NOT NULL DEFAULT true, created_at timestamptz NOT NULL DEFAULT now())""")
    execute(f"""CREATE TABLE IF NOT EXISTS {APP_SCHEMA}.request_log (
        id bigserial PRIMARY KEY, ts timestamptz NOT NULL DEFAULT now(), route text, method text,
        status int, duration_ms double precision, key_label text, detail jsonb)""")
    for raw, label, scope, account in (
        ("rr_demo_portfolio", "portfolio operator", "portfolio", None),
        ("rr_demo_brand_0000", "Aster Lane (ACC-0000)", "brand", "ACC-0000"),
        ("rr_demo_brand_0001", "Brindle Athletics (ACC-0001)", "brand", "ACC-0001"),
        ("rr_demo_brand_0118", "Saffron Beauty (ACC-0118)", "brand", "ACC-0118"),
        ("rr_demo_brand_0094", "Orchard Beauty (ACC-0094)", "brand", "ACC-0094"),
    ):
        execute(f"""INSERT INTO {APP_SCHEMA}.api_keys (key_hash, label, scope, account_id)
                    VALUES (%s, %s, %s, %s) ON CONFLICT (key_hash) DO NOTHING""",
                (key_hash(raw), label, scope, account))


def log_request(route: str, method: str, status: int, duration_ms: float, key_label: str | None, detail: dict | None = None) -> None:
    import json
    try:
        execute(f"INSERT INTO {APP_SCHEMA}.request_log (route, method, status, duration_ms, key_label, detail) "
                "VALUES (%s, %s, %s, %s, %s, %s)", (route, method, status, duration_ms, key_label, json.dumps(detail or {})))
    except Exception:
        pass  # logging must never break a request
