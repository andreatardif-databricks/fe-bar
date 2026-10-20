"""Business-facing access to persisted GenAI recommendations served by Lakebase."""
from fastapi import APIRouter, Depends
from ..auth import require_obo
from .. import db

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
