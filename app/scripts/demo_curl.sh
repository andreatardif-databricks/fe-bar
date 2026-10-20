#!/bin/bash
# Traackr Influencer Revenue API — end-to-end freshness demo.
# Requires env vars:
#   API       e.g. https://<your-app-host>
#   KEY       default pk_demo_coach
#   BRAND_ID  default ACC-00001

set -euo pipefail
: "${API:?API URL required}"
: "${KEY:=pk_demo_coach}"
: "${BRAND_ID:=ACC-00001}"

echo "→ renewal-health"
curl -fsS -H "X-Brand-API-Key: $KEY" "$API/v1/brands/$BRAND_ID/renewal-health" | jq

echo "→ creators (looking for CR-00042)"
curl -fsS -H "X-Brand-API-Key: $KEY" "$API/v1/brands/$BRAND_ID/creators" \
  | jq '.creators[] | select(.creator_id=="CR-00042")'

echo "(Now flip CR-00042 to paused via the orchestration job; sleeping 90s)"
sleep 90

echo "→ creators (CR-00042 should now be 'paused')"
curl -fsS -H "X-Brand-API-Key: $KEY" "$API/v1/brands/$BRAND_ID/creators" \
  | jq '.creators[] | select(.creator_id=="CR-00042")'

echo "→ freshness (requires Databricks OBO from a logged-in user)"
curl -fsS "$API/v1/freshness" | jq
