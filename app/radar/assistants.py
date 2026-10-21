"""Genie (as the signed-in user) and an on-demand model explanation, both traced and logged."""
import os
import time

import mlflow
from databricks.sdk import WorkspaceClient
from databricks.sdk.core import Config
from databricks.sdk.service.serving import ChatMessage, ChatMessageRole
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from . import security, store
from .security import Caller

router = APIRouter(prefix="/v1")
SPACE_ID = os.environ.get("GENIE_SPACE_ID", "")
HOST = os.environ.get("DATABRICKS_HOST", "")
HOST = HOST if HOST.startswith("http") else f"https://{HOST}"
SERVING_ENDPOINT = os.environ.get("SERVING_ENDPOINT", "databricks-claude-haiku-5-5")
APP_URL = os.environ.get("RADAR_PUBLIC_URL", "")

# API-intent questions get an executable call instead of SQL
API_CATALOG = [
    (("renewal", "risk"), "GET", "/v1/brands/{account_id}/renewal-health", "Modelled churn probability, band and drivers"),
    (("campaign", "roi"), "GET", "/v1/brands/{account_id}/campaigns", "Campaign spend, revenue and ROI"),
    (("recommend", "action"), "GET", "/v1/brands/{account_id}/recommendations", "Persisted ai_gen actions"),
    (("portfolio",), "GET", "/v1/portfolio/risk", "Brands ranked by renewal risk (portfolio key)"),
    (("creator",), "GET", "/v1/creators", "Creator roster by tier and region"),
]


class Question(BaseModel):
    question: str


class Explain(BaseModel):
    campaign_id: str


def _api_script(question: str) -> dict | None:
    q = question.lower()
    if not any(w in q for w in ("api", "endpoint", "curl", "call")):
        return None
    for words, method, path, purpose in API_CATALOG:
        if all(w in q for w in words) or (len(words) == 1 and words[0] in q):
            url = f"{APP_URL}{path.replace('{account_id}', 'ACC-0000')}"
            return {"method": method, "path": path, "purpose": purpose,
                    "script": f"curl -s -X {method} '{url}' \\\n  -H 'X-Api-Key: rr_demo_portfolio' -H 'Accept: application/json'"}
    return None


@router.post("/genie/ask", operation_id="askGenie", summary="Ask the curated Genie space (runs as the signed-in user)")
def ask_genie(body: Question, x_forwarded_access_token: str | None = Header(default=None, alias="X-Forwarded-Access-Token")):
    if not x_forwarded_access_token:
        raise HTTPException(401, "Genie runs as the signed-in user; open the app through the workspace")
    t0 = time.perf_counter()
    client = WorkspaceClient(config=Config(host=HOST, token=x_forwarded_access_token, auth_type="pat"))
    with mlflow.start_span(name="genie_answer", span_type="AGENT") as span:
        span.set_inputs({"question": body.question, "space_id": SPACE_ID})
        try:
            msg = client.genie.start_conversation_and_wait(space_id=SPACE_ID, content=body.question)
        except Exception as err:
            raise HTTPException(502, f"Genie request failed: {err}") from err
        span.set_outputs({"conversation_id": msg.conversation_id, "status": str(msg.status)})
    answer, queries = [], []
    for att in msg.attachments or []:
        if att.text and att.text.content:
            answer.append(att.text.content)
        if att.query and att.query.query:
            queries.append({"sql": att.query.query, "description": att.query.description})
    api = _api_script(body.question)
    result = {
        "conversation_id": msg.conversation_id, "message_id": msg.id, "status": getattr(msg.status, "value", str(msg.status)),
        "answer": "\n\n".join(answer),
        # an API question shows the call, not the SQL; analytical questions keep inspectable SQL
        "api_call": api, "queries": [] if api else queries,
        "genie_url": f"{HOST}/genie/rooms/{SPACE_ID}/chats/{msg.conversation_id}",
    }
    store.log_request("/v1/genie/ask", "POST", 200, (time.perf_counter() - t0) * 1000, None,
                      {"question": body.question, "conversation_id": msg.conversation_id, "answered": bool(answer or queries)})
    return result


@router.post("/campaigns/explain", operation_id="explainCampaign", summary="Live Foundation Model explanation for one flagged campaign")
def explain(body: Explain, caller: Caller = Depends(security.caller)):
    row = store.one(f'SELECT * FROM "{store.SYNCED_SCHEMA}".synced_campaign_actions WHERE campaign_id = %s', (body.campaign_id,))
    if not row or not caller.can_read(row["account_id"]):
        raise HTTPException(404, "campaign not found")
    prompt = (f"In two sentences, explain to an account manager why '{row['campaign_name']}' needs attention, using only: "
              f"90-day ROI {row['roi_90d']}, regional benchmark {row['benchmark_roi']}, brand renewal risk {row['risk_band']} "
              f"({round(float(row['renewal_risk_score']) * 100)}% modelled). Existing action: {row['recommendation']}")
    t0 = time.perf_counter()
    with mlflow.start_span(name="campaign_explanation", span_type="CHAT_MODEL") as span:
        span.set_inputs({"campaign_id": body.campaign_id, "prompt": prompt})
        resp = WorkspaceClient().serving_endpoints.query(
            name=SERVING_ENDPOINT, messages=[ChatMessage(role=ChatMessageRole.USER, content=prompt)], max_tokens=800)
        content = resp.choices[0].message.content
        # reasoning models return typed blocks; keep only the visible text
        text = content if isinstance(content, str) else " ".join(
            b.get("text", "") if isinstance(b, dict) else getattr(b, "text", "") or ""
            for b in content if (b.get("type") if isinstance(b, dict) else getattr(b, "type", None)) == "text").strip()
        usage = resp.usage.as_dict() if resp.usage else {}
        span.set_outputs({"text": text, "usage": usage})
    ms = (time.perf_counter() - t0) * 1000
    store.log_request("/v1/campaigns/explain", "POST", 200, ms, caller.label,
                      {"campaign_id": body.campaign_id, "endpoint": SERVING_ENDPOINT, "usage": usage})
    return {"campaign_id": body.campaign_id, "endpoint": SERVING_ENDPOINT, "explanation": text, "usage": usage, "latency_ms": round(ms)}


@router.get("/pipeline/last-run", operation_id="getLastRun", summary="Task-level timings of the latest orchestration run")
def last_run(caller: Caller = Depends(security.caller)):
    security.require_portfolio(caller)
    ws = WorkspaceClient()
    job_id = int(os.environ["RADAR_JOB_ID"])
    run = None
    for candidate in ws.jobs.list_runs(job_id=job_id, completed_only=True, limit=10):
        detail = ws.jobs.get_run(candidate.run_id)
        # partial reruns leave skipped tasks; report the latest run in which every task executed
        if all(getattr(t.state.result_state, "value", None) != "DISABLED" for t in detail.tasks):
            run = detail
            break
    if run is None:
        return {"run": None}
    tasks = [{"task": t.task_key, "result": getattr(t.state.result_state, "value", None),
              "seconds": round(((t.end_time or 0) - (t.start_time or 0)) / 1000)} for t in run.tasks]
    return {"run_id": run.run_id, "result": getattr(run.state.result_state, "value", None),
            "total_seconds": round(((run.end_time or 0) - (run.start_time or 0)) / 1000), "tasks": tasks,
            "url": run.run_page_url}


@router.get("/telemetry/recent", operation_id="recentRequests", summary="Recent request log (portfolio key)")
def recent(caller: Caller = Depends(security.caller)):
    security.require_portfolio(caller)
    return store.rows(f"SELECT ts, route, method, status, round(duration_ms::numeric, 1) AS duration_ms, key_label, detail "
                      f"FROM {store.APP_SCHEMA}.request_log ORDER BY id DESC LIMIT 25")
