"""Persisted AI recommendations and an explicit model-serving demonstration."""
import os
import time

import mlflow
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import ChatMessage, ChatMessageRole
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from ..auth import require_obo
from .. import db
from .. import telemetry

router = APIRouter(prefix="/v1", tags=["AI insights"])
@router.get("/ai-insights")
def ai_insights(_=Depends(require_obo)):
    rows = db.fetch_all(
        f"""
        SELECT campaign_id, account_id, brand_name, campaign_name,
               total_spend_usd, total_revenue_usd, roi,
               recommendation, generated_at, model_function
        FROM {db.SYNCED_SCHEMA}.synced_ai_insights
        ORDER BY total_revenue_usd DESC
        """
    )
    return {"source": "lakebase.synced_ai_insights", "insights": rows}


class RecommendationRequest(BaseModel):
    campaign_name: str = Field(min_length=1, max_length=200)
    spend_usd: float = Field(ge=0)
    attributed_revenue_usd: float = Field(ge=0)
    roi: float


@router.post("/model-recommendation")
def model_recommendation(body: RecommendationRequest, _=Depends(require_obo)):
    trace_id, span_id, started = telemetry.new_trace_context()
    result = _call_model(body)
    duration_ms = (time.perf_counter() - started) * 1000
    telemetry.persist_otel_log(
        trace_id=trace_id,
        span_id=span_id,
        body="Foundation model campaign recommendation completed",
        route="/v1/model-recommendation",
        method="POST",
        status_code=200,
        duration_ms=duration_ms,
        attributes={
            "gen_ai.system": "databricks",
            "gen_ai.request.model": result["endpoint"],
            "campaign.name": body.campaign_name,
            "campaign.roi": str(body.roi),
        },
    )
    return result


@mlflow.trace(name="campaign_model_recommendation", span_type="CHAT_MODEL")
def _call_model(body: RecommendationRequest) -> dict:
    endpoint = os.environ.get("SERVING_ENDPOINT", "databricks-claude-haiku-5-5")
    response = WorkspaceClient().serving_endpoints.query(
        name=endpoint,
        messages=[
            ChatMessage(
                role=ChatMessageRole.SYSTEM,
                content=(
                    "You are an influencer marketing operations analyst. Return one concise "
                    "action grounded only in the supplied metrics. Do not show reasoning."
                ),
            ),
            ChatMessage(
                role=ChatMessageRole.USER,
                content=(
                    f"Campaign: {body.campaign_name}; spend USD: {body.spend_usd:.2f}; "
                    f"attributed revenue USD: {body.attributed_revenue_usd:.2f}; "
                    f"ROI: {body.roi:.3f}. Recommend one action and cite the ROI."
                ),
            ),
        ],
        max_tokens=200,
    )
    if not response.choices or not response.choices[0].message:
        raise RuntimeError("The model endpoint returned no recommendation")
    return {
        "endpoint": endpoint,
        "recommendation": response.choices[0].message.content,
        "usage": response.usage.as_dict() if response.usage else None,
    }
