{
  "name": "Pulsar Influence Co. — Influencer Revenue Pipeline Modernized",
  "columns": [
    {
      "nodes": [
        { "id": "src-salesforce", "label": "Salesforce", "icon": "inputData", "tier": "source", "desc": "Accounts" },
        { "id": "src-hubspot", "label": "HubSpot", "icon": "inputData", "tier": "source", "desc": "Contacts" },
        { "id": "src-google-ads", "label": "Google Ads", "icon": "inputData", "tier": "source", "desc": "Spend" },
        { "id": "src-tiktok", "label": "TikTok API", "icon": "inputData", "tier": "source", "desc": "Engagement" },
        { "id": "src-stripe", "label": "Stripe", "icon": "inputData", "tier": "source", "desc": "Revenue" },
        { "id": "src-s3", "label": "Cloud Storage", "icon": "inputData", "tier": "source", "desc": "Contracts (S3)" }
      ]
    },
    {
      "nodes": [
        { "id": "ingest", "label": "Lakeflow Connect", "icon": "lakeflowConnect", "tier": "ingest", "desc": "Managed Connectors" }
      ]
    },
    {
      "group": { "label": "SDP Pipeline (DAB)", "tier": "sdp" },
      "nodes": [
        { "id": "bronze", "label": "Bronze Layer", "icon": "deltaTable", "tier": "bronze", "desc": "Raw Ingest" },
        { "id": "silver", "label": "Silver Layer", "icon": "deltaTable", "tier": "silver", "desc": "Materialized Views" },
        { "id": "gold", "label": "Gold Layer", "icon": "deltaTable", "tier": "gold", "desc": "Materialized Views" },
        { "id": "platinum", "label": "Platinum Layer", "icon": "streaming", "tier": "gold", "desc": "Streaming + AUTO CDC", "row": 3 }
      ]
    },
    {
      "nodes": [
        { "id": "metric-views", "label": "Metric Views", "icon": "metricViews", "tier": "analytics", "desc": "Governed KPIs", "row": 0 },
        { "id": "lakebase", "label": "Lakebase", "icon": "lakebase", "tier": "compute", "desc": "Autoscaled Postgres (Triggered Sync)", "row": 1.5 }
      ]
    },
    {
      "nodes": [
        { "id": "api", "label": "Customer-Facing API", "icon": "databricksApps", "tier": "analytics", "desc": "FastAPI on Databricks Apps", "row": 1 }
      ]
    },
    {
      "nodes": [
        { "id": "users-brand", "label": "Users", "icon": "businessUser", "tier": "consumer", "desc": "Brand Client Portals", "row": 1 }
      ]
    }
  ],
  "edges": [
    { "from": "src-salesforce", "to": "ingest", "animated": true },
    { "from": "src-hubspot", "to": "ingest", "animated": true },
    { "from": "src-google-ads", "to": "ingest", "animated": true },
    { "from": "src-tiktok", "to": "ingest", "animated": true },
    { "from": "src-stripe", "to": "ingest", "animated": true },
    { "from": "src-s3", "to": "ingest", "animated": true },
    { "from": "ingest", "to": "bronze", "label": "Auto Loader", "animated": true },
    { "from": "bronze", "to": "silver", "label": "MV", "animated": true },
    { "from": "silver", "to": "gold", "label": "MV", "animated": true },
    { "from": "gold", "to": "platinum", "label": "AUTO CDC", "animated": true },
    { "from": "platinum", "to": "metric-views" },
    { "from": "platinum", "to": "lakebase", "label": "Triggered Sync", "animated": true },
    { "from": "lakebase", "to": "api" },
    { "from": "api", "to": "users-brand" }
  ],
  "bars": [
    { "label": "Lakeflow Jobs — Orchestration (Databricks Asset Bundle)", "tier": "orchestration", "startColumn": 1, "endColumn": 4 },
    { "label": "Unity Catalog — Governance & Security", "tier": "governance", "startColumn": 0, "endColumn": 5 }
  ]
}
