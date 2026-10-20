# Unity Catalog and Data Evidence

Catalog and schema: `at_10526_workspace.influencer_engagement_fe_bar`

Query executed after the Lakeflow run:

```sql
SELECT 'bronze_salesforce_accounts' AS object, COUNT(*) AS rows
FROM at_10526_workspace.influencer_engagement_fe_bar.bronze_salesforce_accounts
UNION ALL SELECT 'silver_campaigns', COUNT(*) FROM at_10526_workspace.influencer_engagement_fe_bar.silver_campaigns
UNION ALL SELECT 'gold_campaign_roi', COUNT(*) FROM at_10526_workspace.influencer_engagement_fe_bar.gold_campaign_roi
UNION ALL SELECT 'platinum_brand_360', COUNT(*) FROM at_10526_workspace.influencer_engagement_fe_bar.platinum_brand_360
UNION ALL SELECT 'ai_campaign_insights', COUNT(*) FROM at_10526_workspace.influencer_engagement_fe_bar.ai_campaign_insights;
```

Output:

```json
[
  {"object":"bronze_salesforce_accounts","rows":"600"},
  {"object":"silver_campaigns","rows":"6000"},
  {"object":"gold_campaign_roi","rows":"2000"},
  {"object":"platinum_brand_360","rows":"200"},
  {"object":"ai_campaign_insights","rows":"8"}
]
```

Governed resources also include managed `raw_data` and `cdc_events` volumes, quality expectations on Bronze streaming tables, table comments, and metric views for creator ROI, campaign revenue, and renewal health.
