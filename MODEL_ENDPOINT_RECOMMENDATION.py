"""Call a Databricks foundation-model endpoint with governed campaign metrics."""
import os

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import ChatMessage, ChatMessageRole

ENDPOINT_NAME = os.getenv("SERVING_ENDPOINT", "databricks-claude-haiku-5-5")


def recommend(campaign_name: str, spend_usd: float, revenue_usd: float, roi: float) -> str:
    workspace = WorkspaceClient()
    response = workspace.serving_endpoints.query(
        name=ENDPOINT_NAME,
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
                    f"Campaign: {campaign_name}; spend USD: {spend_usd:.2f}; "
                    f"attributed revenue USD: {revenue_usd:.2f}; ROI: {roi:.3f}. "
                    "Recommend one action and cite the ROI."
                ),
            ),
        ],
        max_tokens=200,
    )
    if not response.choices or not response.choices[0].message:
        raise RuntimeError("The model endpoint returned no recommendation")
    return response.choices[0].message.content or ""


if __name__ == "__main__":
    print(
        recommend(
            campaign_name="Holiday Glow",
            spend_usd=125000,
            revenue_usd=187500,
            roi=1.5,
        )
    )
