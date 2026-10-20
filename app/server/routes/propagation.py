"""
Live change-propagation routes.

POST /v1/admin/propagation/changes injects a single CDC parquet file into
cdc_events/{creators,campaigns}/, persists a tracking row in
public.propagation_changes, and triggers the SDP pipeline plus the relevant
Lakebase synced-table refresh. generate_demo_data is never invoked.

GET  /v1/admin/propagation/targets returns the demoable entities/fields for
the active brand so the UI can populate dropdowns.

GET  /v1/admin/propagation/changes/{change_id}/status (Phase 2) polls the
per-stage timestamps and computes latencies.
"""
from __future__ import annotations
import io
import os
import uuid
from datetime import datetime, timezone
from typing import Literal, Optional, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from databricks.sdk import WorkspaceClient
from .. import db
from ..auth import require_obo

router = APIRouter(prefix="/v1/admin/propagation", tags=["propagation"])

CATALOG = os.environ.get("UC_CATALOG", "at_10526_workspace")
SCHEMA = os.environ.get(
    "UC_SCHEMA",
    "influencer_engagement_fe_bar",
)
CDC_VOLUME_ROOT = f"/Volumes/{CATALOG}/{SCHEMA}/cdc_events"
WAREHOUSE_ID = os.environ.get("WAREHOUSE_ID", "70662a24f8050a48")
SDP_PIPELINE_ID = os.environ.get(
    "SDP_PIPELINE_ID", "93708933-2ab0-44c5-a6ff-76ea16d21523",
)
SYNCED_PIPELINE_ID = {
    "creator":  os.environ.get("SYNCED_CREATORS_PIPELINE_ID",  "08f648b7-4689-4abd-ba6e-bffee3ea1086"),
    "campaign": os.environ.get("SYNCED_CAMPAIGNS_PIPELINE_ID", "b65659f6-edea-43f7-8a6d-d4ef438670d3"),
}

# Phase 0 + user confirmation: limit dropdown to these fields per entity
ALLOWED_FIELDS = {
    "creator":  {"display_name", "status", "tier"},
    "campaign": {"status", "name"},
}
ALLOWED_VALUES = {
    ("creator", "status"):  {"active", "paused", "under_review", "offboarded"},
    ("creator", "tier"):    {"nano", "micro", "mid", "macro"},
    ("campaign", "status"): {"active", "paused", "ended"},
}


# ----------------------------- GET /targets -----------------------------

@router.get("/targets")
def list_targets(brand_id: str, _=Depends(require_obo)):
    """Return demoable entities + current values for the given brand."""
    creators = db.fetch_all(
        f"""
        SELECT creator_id, handle, display_name, tier, platform, country, status, follower_count
        FROM {db.SYNCED_SCHEMA}.synced_creators
        WHERE agent_email = 'maya.patel@pulsar.com'
        ORDER BY follower_count DESC NULLS LAST
        LIMIT 20
        """
    )
    campaigns = db.fetch_all(
        f"""
        SELECT campaign_id, name, status, start_date, end_date, budget_usd
        FROM {db.SYNCED_SCHEMA}.synced_campaigns
        WHERE account_id = %s
        ORDER BY (status = 'active') DESC, end_date DESC NULLS LAST
        LIMIT 50
        """,
        (brand_id,),
    )
    return {
        "brand_id": brand_id,
        "creators": creators,
        "campaigns": campaigns,
        "allowed_fields": {k: sorted(v) for k, v in ALLOWED_FIELDS.items()},
        "allowed_values": {f"{e}.{f}": sorted(vals) for (e, f), vals in ALLOWED_VALUES.items()},
    }


# ----------------------------- POST /changes -----------------------------

class ChangeBody(BaseModel):
    entity: Literal["creator", "campaign"]
    entity_id: str = Field(..., min_length=1, max_length=64)
    field: str = Field(..., min_length=1, max_length=64)
    new_value: str = Field(..., min_length=1, max_length=200)
    brand_id: Optional[str] = None


class _NotYet(Exception):
    """The warehouse query did not finish within wait_timeout. Treat as 'not observed yet'."""


def _warehouse_sql(stmt: str, *, timeout: str = "20s") -> list[list[Any]]:
    """Run a SQL statement on the warehouse as the app SP. Returns raw rows.

    Raises:
        _NotYet:   if the statement is still PENDING/RUNNING when wait_timeout fires
                   (caller treats as 'condition not yet met', not an error).
        HTTPException(503): if the statement actually FAILED or CANCELED.
    """
    w = WorkspaceClient()
    res = w.statement_execution.execute_statement(
        warehouse_id=WAREHOUSE_ID,
        statement=stmt,
        wait_timeout=timeout,
    )
    state = res.status.state.value if res.status and res.status.state else "?"
    if state in ("PENDING", "RUNNING"):
        raise _NotYet(state)
    if state != "SUCCEEDED":
        err = res.status.error.message if res.status and res.status.error else state
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, f"warehouse SQL: {err}")
    return (res.result.data_array or []) if res.result else []


def _next_seq(entity: str) -> int:
    table = "bronze_cdc_creators" if entity == "creator" else "bronze_cdc_campaigns"
    try:
        rows = _warehouse_sql(f"SELECT COALESCE(MAX(seq), 0) + 1 FROM {CATALOG}.{SCHEMA}.{table}", timeout="30s")
    except _NotYet:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "warehouse is still spinning up; retry in a few seconds")
    if not rows or not rows[0]:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "could not read MAX(seq) from bronze")
    return int(rows[0][0])


def _current_state(entity: str, entity_id: str) -> dict | None:
    """Read the current platinum row so we can build a payload that only changes one field."""
    safe_id = entity_id.replace("'", "''")
    try:
        if entity == "creator":
            rows = _warehouse_sql(
                f"SELECT creator_id, handle, display_name, tier, platform, country, "
                f"follower_count, status, agent_email, joined_at, updated_at "
                f"FROM {CATALOG}.{SCHEMA}.platinum_creator_360 WHERE creator_id = '{safe_id}'",
                timeout="30s",
            )
            keys = ["creator_id", "handle", "display_name", "tier", "platform", "country",
                    "follower_count", "status", "agent_email", "joined_at", "updated_at"]
        else:
            rows = _warehouse_sql(
                f"SELECT campaign_id, account_id, name, start_date, end_date, budget_usd, "
                f"status, created_at, updated_at "
                f"FROM {CATALOG}.{SCHEMA}.platinum_campaign_360 WHERE campaign_id = '{safe_id}'",
                timeout="30s",
            )
            keys = ["campaign_id", "account_id", "name", "start_date", "end_date", "budget_usd",
                    "status", "created_at", "updated_at"]
    except _NotYet:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "warehouse is still spinning up; retry in a few seconds")
    if not rows:
        return None
    return dict(zip(keys, rows[0]))


def _coerce(entity: str, field: str, raw: str) -> Any:
    if entity == "creator" and field == "follower_count":
        return int(raw)
    if entity == "campaign" and field == "budget_usd":
        return float(raw)
    return str(raw)


def _parse_ts(v: Any) -> datetime:
    """Coerce a Statement-Execution result (string or datetime) into a naive UTC datetime."""
    if v is None:
        return datetime.now(timezone.utc).replace(tzinfo=None)
    if isinstance(v, datetime):
        return v.replace(tzinfo=None) if v.tzinfo else v
    s = str(v).replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
        return dt.replace(tzinfo=None) if dt.tzinfo else dt
    except Exception:
        return datetime.now(timezone.utc).replace(tzinfo=None)


def _parse_date(v: Any):
    from datetime import date
    if v is None:
        return None
    if isinstance(v, date) and not isinstance(v, datetime):
        return v
    try:
        return datetime.strptime(str(v)[:10], "%Y-%m-%d").date()
    except Exception:
        return None


def _build_creator_parquet(payload: dict, *, event_id: str, seq: int, op: str, ts: datetime) -> bytes:
    import pyarrow as pa
    import pyarrow.parquet as pq
    payload_struct = pa.struct([
        pa.field("creator_id",     pa.string()),
        pa.field("handle",         pa.string()),
        pa.field("display_name",   pa.string()),
        pa.field("tier",           pa.string()),
        pa.field("platform",       pa.string()),
        pa.field("country",        pa.string()),
        pa.field("follower_count", pa.int64()),
        pa.field("status",         pa.string()),
        pa.field("agent_email",    pa.string()),
        pa.field("joined_at",      pa.timestamp("us")),
        pa.field("updated_at",     pa.timestamp("us")),
    ])
    schema = pa.schema([
        pa.field("event_id",   pa.string()),
        pa.field("creator_id", pa.string()),
        pa.field("op",         pa.string()),
        pa.field("seq",        pa.int64()),
        pa.field("timestamp",  pa.timestamp("us")),
        pa.field("payload",    payload_struct),
    ])
    table = pa.Table.from_pylist([{
        "event_id":   event_id,
        "creator_id": payload["creator_id"],
        "op":         op,
        "seq":        seq,
        "timestamp":  ts,
        "payload": {
            "creator_id":     payload["creator_id"],
            "handle":         payload.get("handle"),
            "display_name":   payload.get("display_name"),
            "tier":           payload.get("tier"),
            "platform":       payload.get("platform"),
            "country":        payload.get("country"),
            "follower_count": int(payload["follower_count"]) if payload.get("follower_count") is not None else None,
            "status":         payload.get("status"),
            "agent_email":    payload.get("agent_email"),
            "joined_at":      _parse_ts(payload.get("joined_at")),
            "updated_at":     _parse_ts(payload.get("updated_at")),
        },
    }], schema=schema)
    buf = io.BytesIO()
    pq.write_table(table, buf, compression="snappy")
    return buf.getvalue()


def _build_campaign_parquet(payload: dict, *, event_id: str, seq: int, op: str, ts: datetime) -> bytes:
    import pyarrow as pa
    import pyarrow.parquet as pq
    payload_struct = pa.struct([
        pa.field("campaign_id", pa.string()),
        pa.field("account_id",  pa.string()),
        pa.field("name",        pa.string()),
        pa.field("start_date",  pa.date32()),
        pa.field("end_date",    pa.date32()),
        pa.field("budget_usd",  pa.float64()),
        pa.field("status",      pa.string()),
        pa.field("created_at",  pa.timestamp("us")),
        pa.field("updated_at",  pa.timestamp("us")),
    ])
    schema = pa.schema([
        pa.field("event_id",    pa.string()),
        pa.field("campaign_id", pa.string()),
        pa.field("op",          pa.string()),
        pa.field("seq",         pa.int64()),
        pa.field("timestamp",   pa.timestamp("us")),
        pa.field("payload",     payload_struct),
    ])
    table = pa.Table.from_pylist([{
        "event_id":    event_id,
        "campaign_id": payload["campaign_id"],
        "op":          op,
        "seq":         seq,
        "timestamp":   ts,
        "payload": {
            "campaign_id": payload["campaign_id"],
            "account_id":  payload.get("account_id"),
            "name":        payload.get("name"),
            "start_date":  _parse_date(payload.get("start_date")),
            "end_date":    _parse_date(payload.get("end_date")),
            "budget_usd":  float(payload["budget_usd"]) if payload.get("budget_usd") is not None else None,
            "status":      payload.get("status"),
            "created_at":  _parse_ts(payload.get("created_at")),
            "updated_at":  _parse_ts(payload.get("updated_at")),
        },
    }], schema=schema)
    buf = io.BytesIO()
    pq.write_table(table, buf, compression="snappy")
    return buf.getvalue()


@router.post("/changes", status_code=status.HTTP_201_CREATED)
def create_change(body: ChangeBody, _=Depends(require_obo)):
    # 1. Validate inputs
    if body.field not in ALLOWED_FIELDS[body.entity]:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
            f"field '{body.field}' is not demoable for {body.entity}. "
            f"Allowed: {sorted(ALLOWED_FIELDS[body.entity])}")
    val_set = ALLOWED_VALUES.get((body.entity, body.field))
    if val_set is not None and body.new_value not in val_set:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
            f"value '{body.new_value}' not allowed for {body.entity}.{body.field}. "
            f"Allowed: {sorted(val_set)}")

    # 2. Read current row from platinum
    state = _current_state(body.entity, body.entity_id)
    if not state:
        raise HTTPException(status.HTTP_404_NOT_FOUND,
            f"{body.entity} {body.entity_id} not found in platinum")

    old_value = state.get(body.field)
    new_value_typed = _coerce(body.entity, body.field, body.new_value)

    if str(old_value) == str(new_value_typed):
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
            f"new_value is the same as current ({old_value!r}); pick a different value to see propagation")

    # 3. Build the CDC event
    change_id = uuid.uuid4().hex
    seq = _next_seq(body.entity)
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    payload = dict(state)
    payload[body.field] = new_value_typed
    payload["updated_at"] = now_utc

    if body.entity == "creator":
        event_id = f"EV-CR-{seq:08d}"
        parquet_bytes = _build_creator_parquet(payload, event_id=event_id, seq=seq, op="UPSERT", ts=now_utc)
        volume_subdir = "creators"
    else:
        event_id = f"EV-CMP-{seq:08d}"
        parquet_bytes = _build_campaign_parquet(payload, event_id=event_id, seq=seq, op="UPSERT", ts=now_utc)
        volume_subdir = "campaigns"

    target_path = f"{CDC_VOLUME_ROOT}/{volume_subdir}/change_{change_id}.parquet"

    # 4. Upload the parquet
    w = WorkspaceClient()
    try:
        w.files.upload(target_path, io.BytesIO(parquet_bytes), overwrite=False)
    except Exception as e:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR,
            f"failed to write CDC event to {target_path}: {e}")
    t_raw = datetime.now(timezone.utc)

    # 5. Persist tracking row
    brand_id = body.brand_id
    if body.entity == "campaign" and not brand_id:
        brand_id = state.get("account_id")
    try:
        with db.get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO public.propagation_changes
                      (change_id, entity, entity_id, field, old_value, new_value,
                       brand_id, sequence_no, t_raw)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (change_id, body.entity, body.entity_id, body.field,
                     str(old_value) if old_value is not None else None,
                     str(new_value_typed), brand_id, seq, t_raw),
                )
    except Exception as e:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR,
            f"failed to persist tracking row: {e}")

    # 6. Trigger SDP pipeline + the relevant synced-table refresh
    run_id, sync_run_id, trigger_err = None, None, None
    try:
        sdp_update = w.pipelines.start_update(pipeline_id=SDP_PIPELINE_ID, full_refresh=False)
        run_id = getattr(sdp_update, "update_id", None) or getattr(sdp_update, "request_id", None)
    except Exception as e:
        trigger_err = f"SDP pipeline trigger failed: {e}"

    try:
        sync_pid = SYNCED_PIPELINE_ID[body.entity]
        sync_update = w.pipelines.start_update(pipeline_id=sync_pid, full_refresh=False)
        sync_run_id = getattr(sync_update, "update_id", None) or getattr(sync_update, "request_id", None)
    except Exception as e:
        trigger_err = (trigger_err + " | " if trigger_err else "") + f"synced-table trigger failed: {e}"

    if run_id or sync_run_id or trigger_err:
        try:
            with db.get_pool().connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE public.propagation_changes SET run_id = %s, sync_run_id = %s, error = %s WHERE change_id = %s",
                        (run_id, sync_run_id, trigger_err, change_id),
                    )
        except Exception:
            pass

    return {
        "change_id": change_id,
        "entity": body.entity,
        "entity_id": body.entity_id,
        "field": body.field,
        "old_value": str(old_value) if old_value is not None else None,
        "new_value": str(new_value_typed),
        "brand_id": brand_id,
        "sequence_no": seq,
        "event_id": event_id,
        "volume_path": target_path,
        "run_id": run_id,
        "sync_run_id": sync_run_id,
        "t_raw": t_raw.isoformat(),
        "trigger_error": trigger_err,
    }


# ----------------------------- GET /changes/{change_id}/status -----------------------------

def _bronze_seen(entity: str, entity_id: str, sequence_no: int) -> bool:
    table = "bronze_cdc_creators" if entity == "creator" else "bronze_cdc_campaigns"
    key_col = "creator_id" if entity == "creator" else "campaign_id"
    safe = entity_id.replace("'", "''")
    rows = _warehouse_sql(
        f"SELECT 1 FROM {CATALOG}.{SCHEMA}.{table} "
        f"WHERE {key_col} = '{safe}' AND seq = {int(sequence_no)} LIMIT 1",
        timeout="15s",
    )
    return bool(rows)


def _platinum_seen(entity: str, entity_id: str, field: str, new_value: str) -> bool:
    if entity == "creator":
        table, key_col = "platinum_creator_360", "creator_id"
    else:
        table, key_col = "platinum_campaign_360", "campaign_id"
    safe_id = entity_id.replace("'", "''")
    safe_v = str(new_value).replace("'", "''")
    rows = _warehouse_sql(
        f"SELECT 1 FROM {CATALOG}.{SCHEMA}.{table} "
        f"WHERE {key_col} = '{safe_id}' AND {field} = '{safe_v}' LIMIT 1",
        timeout="15s",
    )
    return bool(rows)


def _lakebase_seen(entity: str, entity_id: str, field: str, new_value: str) -> bool:
    table = "synced_creators" if entity == "creator" else "synced_campaigns"
    key_col = "creator_id" if entity == "creator" else "campaign_id"
    row = db.fetch_one(
        f"SELECT 1 AS x FROM {db.SYNCED_SCHEMA}.{table} WHERE {key_col} = %s AND {field} = %s LIMIT 1",
        (entity_id, new_value),
    )
    return bool(row)


def _find_key_for_brand(brand_id: str) -> Optional[str]:
    """Locate any active API key that grants access to brand_id."""
    row = db.fetch_one(
        f"""
        SELECT api_key FROM public.api_keys
        WHERE is_active
          AND (
            brand_scope = 'all'
            OR (brand_scope = 'account_id' AND brand_id = %s)
            OR (brand_scope = 'brand_name'
                AND brand_id = (SELECT brand_name FROM {db.SYNCED_SCHEMA}.synced_brands WHERE account_id = %s LIMIT 1))
          )
        ORDER BY (brand_scope = 'account_id') DESC, (brand_scope = 'brand_name') DESC
        LIMIT 1
        """,
        (brand_id, brand_id),
    )
    return row["api_key"] if row else None


def _api_seen(brand_id: str, entity: str, entity_id: str, field: str, new_value: str) -> bool:
    """Self-call the real public route with a valid key and confirm new_value is present."""
    if not brand_id:
        return False
    api_key = _find_key_for_brand(brand_id)
    if not api_key:
        return False
    import urllib.parse, urllib.request, json as jsonlib
    if entity == "creator":
        path = f"/v1/brands/{urllib.parse.quote(brand_id)}/creators?status=all&limit=200"
        items_key, id_key = "creators", "creator_id"
    else:
        path = f"/v1/brands/{urllib.parse.quote(brand_id)}/campaigns?status=all&limit=200"
        items_key, id_key = "campaigns", "campaign_id"
    url = f"http://127.0.0.1:{os.environ.get('DATABRICKS_APP_PORT', '8000')}{path}"
    req = urllib.request.Request(url, headers={"X-Brand-API-Key": api_key, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = jsonlib.loads(resp.read())
    except Exception:
        return False
    for item in data.get(items_key, []) or []:
        if str(item.get(id_key)) == str(entity_id) and str(item.get(field)) == str(new_value):
            return True
    return False


def _retrigger_sync(entity: str) -> str | None:
    """Re-trigger the synced-table pipeline once the platinum stage has caught up."""
    try:
        w = WorkspaceClient()
        upd = w.pipelines.start_update(pipeline_id=SYNCED_PIPELINE_ID[entity], full_refresh=False)
        return getattr(upd, "update_id", None) or getattr(upd, "request_id", None)
    except Exception:
        return None


@router.get("/changes/{change_id}/status")
def get_status(change_id: str, _=Depends(require_obo)):
    row = db.fetch_one(
        "SELECT * FROM public.propagation_changes WHERE change_id = %s",
        (change_id,),
    )
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "change not found")

    entity = row["entity"]
    entity_id = row["entity_id"]
    field = row["field"]
    new_value = row["new_value"]
    sequence_no = int(row["sequence_no"])
    brand_id = row["brand_id"]
    t_raw = row["t_raw"]
    t_bronze = row["t_bronze"]
    t_platinum = row["t_platinum"]
    t_lakebase = row["t_lakebase"]
    t_api = row["t_api"]
    sync_retriggered = bool(row.get("sync_retriggered"))
    sync_run_id = row.get("sync_run_id")
    err = row.get("error")

    updates: dict[str, Any] = {}
    now = lambda: datetime.now(timezone.utc)

    if t_bronze is None:
        try:
            if _bronze_seen(entity, entity_id, sequence_no):
                t_bronze = now(); updates["t_bronze"] = t_bronze
        except _NotYet:
            pass  # warehouse still pending, try again next poll
        except HTTPException as e:
            err = (err + " | " if err else "") + f"bronze check: {e.detail}"

    if t_platinum is None:
        try:
            if _platinum_seen(entity, entity_id, field, new_value):
                t_platinum = now(); updates["t_platinum"] = t_platinum
        except _NotYet:
            pass
        except HTTPException as e:
            err = (err + " | " if err else "") + f"platinum check: {e.detail}"

    if t_platinum is not None and t_lakebase is None and not sync_retriggered:
        new_id = _retrigger_sync(entity)
        if new_id:
            sync_run_id = new_id
            updates["sync_run_id"] = new_id
        sync_retriggered = True
        updates["sync_retriggered"] = True

    if t_lakebase is None:
        try:
            if _lakebase_seen(entity, entity_id, field, new_value):
                t_lakebase = now(); updates["t_lakebase"] = t_lakebase
        except Exception as e:
            err = (err + " | " if err else "") + f"lakebase check: {e}"

    if t_api is None and t_lakebase is not None:
        if _api_seen(brand_id, entity, entity_id, field, new_value):
            t_api = now(); updates["t_api"] = t_api

    if err and err != row.get("error"):
        updates["error"] = err

    if updates:
        cols = list(updates.keys())
        sets = ", ".join(f"{c} = %s" for c in cols)
        params = [updates[c] for c in cols] + [change_id]
        try:
            with db.get_pool().connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"UPDATE public.propagation_changes SET {sets} WHERE change_id = %s",
                        params,
                    )
        except Exception:
            pass

    def _iso(ts):
        if ts is None:
            return None
        if isinstance(ts, datetime):
            return (ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)).isoformat()
        return str(ts)

    stages = [
        {"key": "raw",      "label": "Raw source",         "reached": True,                  "at": _iso(t_raw)},
        {"key": "bronze",   "label": "Bronze",             "reached": t_bronze is not None,  "at": _iso(t_bronze)},
        {"key": "platinum", "label": "Platinum (AUTO CDC)","reached": t_platinum is not None,"at": _iso(t_platinum)},
        {"key": "lakebase", "label": "Lakebase sync",      "reached": t_lakebase is not None,"at": _iso(t_lakebase)},
        {"key": "api",      "label": "Public API",         "reached": t_api is not None,     "at": _iso(t_api)},
    ]

    def _ms(a, b):
        if a is None or b is None:
            return None
        # normalise to aware
        a = a if (isinstance(a, datetime) and a.tzinfo) else (a.replace(tzinfo=timezone.utc) if isinstance(a, datetime) else None)
        b = b if (isinstance(b, datetime) and b.tzinfo) else (b.replace(tzinfo=timezone.utc) if isinstance(b, datetime) else None)
        if a is None or b is None:
            return None
        return int((b - a).total_seconds() * 1000)

    per_stage_ms = {
        "bronze":   _ms(t_raw,      t_bronze),
        "platinum": _ms(t_bronze,   t_platinum),
        "lakebase": _ms(t_platinum, t_lakebase),
        "api":      _ms(t_lakebase, t_api),
    }
    total_ms = _ms(t_raw, t_api)

    return {
        "change_id": change_id,
        "entity": entity,
        "entity_id": entity_id,
        "field": field,
        "old_value": row.get("old_value"),
        "new_value": new_value,
        "brand_id": brand_id,
        "sequence_no": sequence_no,
        "stages": stages,
        "per_stage_ms": per_stage_ms,
        "total_ms": total_ms,
        "complete": t_api is not None,
        "sync_retriggered": sync_retriggered,
        "run_id": row.get("run_id"),
        "sync_run_id": sync_run_id,
        "error": err,
    }
