"""User-scoped access to the curated Traackr Genie Agent."""
import json
import os
import time

import mlflow
from fastapi import APIRouter, Header, HTTPException
from databricks.sdk import WorkspaceClient
from databricks.sdk.core import Config
from .. import telemetry

router = APIRouter(prefix="/v1/genie", tags=["Genie Agent"])
SPACE_ID = os.getenv("DATABRICKS_GENIE_SPACE_ID", "01f1cbfef7e81a1d8d9161f8fd8d65f6")
WORKSPACE_HOST = os.environ.get("DATABRICKS_HOST", "https://dbc-01f27b97-0e2e.cloud.databricks.com")
if not WORKSPACE_HOST.startswith(("http://", "https://")):
    WORKSPACE_HOST = f"https://{WORKSPACE_HOST}"
WORKSPACE_ID = os.environ.get("DATABRICKS_WORKSPACE_ID", "7474653524978634")


def user_client(token: str) -> WorkspaceClient:
    return WorkspaceClient(config=Config(
        host=os.environ["DATABRICKS_HOST"],
        token=token,
        auth_type="pat",
    ))


@router.get("/whoami")
def whoami(
    x_forwarded_email: str | None = Header(default=None, alias="X-Forwarded-Email"),
    x_forwarded_user: str | None = Header(default=None, alias="X-Forwarded-User"),
):
    return {"user": x_forwarded_email or x_forwarded_user or "unknown", "execution_identity": "signed-in user (OBO)"}


@router.post("/ask")
def ask_genie(
    payload: dict,
    x_forwarded_access_token: str | None = Header(default=None, alias="X-Forwarded-Access-Token"),
):
    question = str(payload.get("question", "")).strip()
    if not question:
        raise HTTPException(400, "question is required")
    if not x_forwarded_access_token:
        raise HTTPException(401, "Genie requires a signed-in Databricks user token")
    trace_id, span_id, started = telemetry.new_trace_context()
    try:
        with mlflow.start_span(name="genie_agent_answer", span_type="AGENT") as span:
            span.set_inputs({"question": question, "space_id": SPACE_ID})
            message = user_client(x_forwarded_access_token).genie.start_conversation_and_wait(
                space_id=SPACE_ID,
                content=question,
            )
            span.set_outputs({
                "conversation_id": message.conversation_id,
                "message_id": message.id,
                "status": message.status.value if hasattr(message.status, "value") else str(message.status),
            })
    except Exception as error:
        raise HTTPException(502, f"Genie request failed: {error}") from error

    answer_parts = []
    queries = []
    for attachment in message.attachments or []:
        if attachment.text and attachment.text.content:
            answer_parts.append(attachment.text.content)
        if attachment.query and attachment.query.query:
            queries.append({
                "sql": attachment.query.query,
                "description": attachment.query.description,
                "row_count": attachment.query.query_result_metadata.row_count if attachment.query.query_result_metadata else None,
            })
    api_script = None
    normalized_question = question.lower()
    if "api" in normalized_question or "endpoint" in normalized_question:
        if "renewal" in normalized_question:
            api_script = """curl --request GET \\
  --url 'https://influencer-fe-bar-7474653524978634.aws.databricksapps.com/v1/brands/ACC-00001/renewal-health' \\
  --header 'Accept: application/json' \\
  --header 'X-Brand-API-Key: pk_demo_all'"""
    result = {
        "space_id": SPACE_ID,
        "conversation_id": message.conversation_id,
        "message_id": message.id,
        "status": message.status.value if hasattr(message.status, "value") else str(message.status),
        "answer": "\n\n".join(answer_parts),
        "queries": queries,
        "api_script": api_script,
        "genie_url": f"{WORKSPACE_HOST}/genie/rooms/{SPACE_ID}?o={WORKSPACE_ID}",
        "disclaimer": "AI-generated — verify the API script and governed source data." if api_script else "AI-generated — verify against the generated SQL and governed source tables.",
    }
    telemetry.persist_otel_log(
        trace_id=trace_id,
        span_id=span_id,
        body=json.dumps({
            "question": question,
            "answer": result["answer"],
            "conversation_id": result["conversation_id"],
            "message_id": result["message_id"],
        }),
        route="/v1/genie/ask",
        method="POST",
        status_code=200,
        duration_ms=(time.perf_counter() - started) * 1000,
        attributes={
            "gen_ai.system": "databricks-genie",
            "gen_ai.agent.id": SPACE_ID,
            "gen_ai.conversation.id": result["conversation_id"],
        },
    )
    return result
