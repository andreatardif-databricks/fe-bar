# Protect $200K by moving influencer budget sooner
## A governed operational-intelligence product for a global consumer brand using Traackr

Illustrative case: redirecting 2% of a $10M annual influencer budget · Synthetic data only

---

# The customer and the decision

A global consumer brand runs creator campaigns through Traackr but cannot connect social engagement, media spend, attributed revenue, and renewal health quickly enough to change investment while a campaign is still active.

Marketing leaders need three answers before budget and renewal decisions:

1. Which campaigns and creators are producing efficient attributed revenue?
2. Which brand relationships show renewal risk?
3. What action should the team take now?

Today those answers require fragmented CRM, social, advertising, contract, and billing extracts. This product turns those feeds into governed KPIs, operational APIs, and grounded AI recommendations in one integrated flow.

**Illustrative value:** On $10M in annual influencer spend, identifying and redirecting 2% of inefficient investment protects **$200K per year**. The measured demo reduces raw-event-to-API availability from a next-day handoff to **4 minutes 22 seconds**.

---

# Buyer value

## Executive sponsor: Chief Marketing Officer

- Reallocate influencer spend using attributed revenue and ROI.
- Protect renewal ARR with a consistent health signal.
- Replace manual performance interpretation with persisted, auditable AI recommendations.
- Improve the measures the CMO is evaluated on: marketing efficiency, attributed revenue, and retention of strategic brand investment.

## Domain owner: Influencer Marketing Operations

- Serve current campaign and creator data to brand portals through Lakebase-backed APIs.
- Observe event-to-API propagation and measured latency.
- Ask governed natural-language questions without writing SQL.
- Improve the measures operations owns: time to insight, data-freshness SLA, recommendation adoption, and API reliability.

---

# The integrated data product

`Synthetic Salesforce + HubSpot + TikTok + Google Ads + Stripe + contracts`

→ `Unity Catalog Volumes`

→ `Lakeflow Bronze / Silver / Gold / Platinum`

→ `ai_gen + Foundation Model API recommendations`

→ `Lakebase synced operational tables`

→ `FastAPI on Databricks Apps + curated Genie Agent`

Every downstream stage depends on the preceding successful stage in the deployed job.

---

# Synthetic data that tells the story

The executable generator in `src/data_gen/generate.py` creates correlated, reproducible source data—not independent random rows.

- Creator tier determines follower bands from nano (`1K–10K`) through macro (`1M–5M`).
- Campaign status changes spend behavior; account tier changes renewal ARR exposure.
- Stripe includes paid, pending, and refunded transactions; contracts include active, expired, and terminated records.
- Ordered CDC feeds include late updates, pauses, reviews, offboarding, and one campaign UPSERT.
- `CR-00042` and `CMP-01337` contain a deliberate creator-campaign revenue surge that drives the ROI and action story.

Actual governed profile after four refreshes:

| Dataset | Rows |
|---|---:|
| TikTok metrics | 4,800,000 |
| Stripe revenue | 401,380 |
| Google Ads spend | 243,460 |
| Creator CDC | 20,024 |
| Campaign CDC | 8,005 |
| Gold creator performance | 2,261,354 |

The headline creator grew from **$5K in June to $402K in September**, with 97–99% of post-launch revenue tied to the headline campaign. Full logic and executed profiles are in `SYNTHETIC_DATA.md`.

---

# Live demonstration

1. Generate synthetic source and CDC records.
2. Run the serverless Lakeflow pipeline incrementally.
3. Persist grounded campaign recommendations with `ai_gen`.
4. Call `databricks-claude-haiku-5-5` through the app's bound model-serving resource.
5. Refresh Lakebase only after the analytical and AI stages succeed.
6. Query the same served records through documented FastAPI endpoints.
7. Push a synthetic change and watch Bronze → Platinum → Lakebase → API latency.
8. Ask Genie for campaign ROI, renewal risk, AI actions, or API guidance.

---

# Intelligence users can trust

- Recommendations use only campaign name, spend, attributed revenue, and ROI.
- Outputs are persisted in Unity Catalog with generation timestamp and function provenance.
- `POST /v1/model-recommendation` calls a declared Foundation Model API resource with `CAN_QUERY` permission.
- The app labels results “AI-generated — verify before acting.”
- Genie is curated to governed tables and includes certified SQL examples.
- Generated SQL and source tables remain inspectable.
- MLflow persists every live model request, output, status, latency, and token usage to governed Unity Catalog tables.
- The app persists OpenTelemetry-shaped request records to the governed `app_otel_logs` UC table.

---

# Decisions and trade-offs

| Decision | Why | Trade-off |
|---|---|---|
| Serve the app from Lakebase | Sub-second operational reads without waking a warehouse | Requires governed lakehouse-to-Lakebase synchronization |
| Persist `ai_gen` recommendations | Auditable, stable default; no LLM inference on page open | Refreshes per orchestration rather than continuously |
| Expose a separate model endpoint route | Proves governed on-demand inference and supports interactive testing | Adds variable latency and token cost, so it is not used for page startup |
| Curate Genie over UC tables | Natural language plus inspectable generated SQL | Genie analytical execution uses a SQL warehouse |
| Use synthetic data | Safe, reproducible, shareable | Value estimates require production calibration |
| Bundle every resource | Repeatable deployment and evidence | Some identity grants require a post-deploy helper |

---

# AI as a force multiplier

- Used an AI coding agent to map rubric requirements, implement original code, deploy, diagnose failures, and capture evidence.
- Prompt pattern: define the customer outcome, require an integrated stage-by-stage journey, and demand readable execution proof.
- Used AI to challenge architecture claims with live tests: endpoint timing, pipeline states, Genie SQL, Lakebase synchronization, and app logs.
- Used `ai_gen` as a product capability, with prompts constrained to governed campaign metrics and persisted outputs.
- Verified a live Foundation Model API call and committed the exact request, response, model name, and token usage as text.
- Preserved both build conversation IDs in `FE_BAR_SUBMISSION.md` for traceability.

---

# Governance by design

- Synthetic data only; no customer records.
- Managed UC schema and volumes with table comments and quality expectations.
- Metric views standardize creator ROI, campaign revenue, and renewal health.
- App resource permissions use its Databricks service principal.
- Brand API keys are scoped and validated in Lakebase.

---

# Evidence, not architecture claims

The repository commits readable text proving:

- Successful job and Lakeflow task execution
- Governed table counts and KPI query results
- Real persisted GenAI recommendations
- Lakebase synchronization and live API responses
- Genie answers with generated SQL
- Stage and end-to-end propagation latency
- MLflow `CHAT_MODEL` traces and app OTEL request logs persisted in UC

Direct execution transcript:

```text
2026-10-20 17:14:46 "[prod] Pulsar — Daily Orchestration" TERMINATED SUCCESS
run_id=1013848902778635 · all five dependent tasks SUCCESS

Genie status=COMPLETED · conversation_id=01f1cce7f0581fcdaed78469249b327a
Question: Which API endpoint shows renewal risk?
Answer: GET /v1/brands/{brand_id}/renewal-health

Model endpoint=databricks-claude-haiku-5-5 · total_tokens=209
MLflow trace status=STATUS_CODE_OK · app OTEL HTTP status=200
```

Start with `RAW_EXECUTION_TRANSCRIPT.md`: it contains successful run `1013848902778635`, every task state, the deployed model response, the MLflow UC trace, and the app OTEL UC row. Then review `EXECUTION_EVIDENCE.md`, `SYNTHETIC_DATA.md`, and `AI_GEN_RECOMMENDATIONS.sql`.

---

# Success measures

- **Data freshness:** operational serving within the five-minute demo SLA.
- **Decision speed:** campaign action available in the same orchestrated run as refreshed KPIs.
- **Adoption:** business and developer questions answered through one curated Genie Agent.
- **Trust:** every KPI, recommendation, and answer traces to governed source data.

---

# Live roleplay: tell — show — tell

## Tell (30 seconds)

“A global consumer brand is losing time and budget because campaign engagement, spend, revenue, and renewal signals arrive in separate systems. This product makes the decision operational in under five minutes and could protect $200K annually on a $10M program.”

## Show (3 minutes)

1. Start on the outcome and Lakebase-served KPIs.
2. Push one synthetic campaign change and narrate the integrated stage tracker.
3. Open AI Recommendations and explain that output is persisted, governed, and served from Lakebase.
4. Call the model-recommendation route and show the returned endpoint name, recommendation, and token usage.
5. Ask Genie which campaign has the highest ROI, then inspect generated SQL.
6. Ask which API exposes renewal risk, then show the executable API script.

## Tell (30 seconds)

“We moved from a raw event to a governed operational API in 4m22s, produced a grounded action without inference at page load, and made the same data accessible to applications and business users.”

---

# Objections to rehearse

**Business stakeholder:** “Is $200K guaranteed?”  
No. It is an explicit planning estimate: 2% of a $10M spend base. Production calibration would replace the assumption with observed reallocation and incremental-revenue outcomes.

**Business stakeholder:** “Why should I trust the recommendation?”  
It is grounded only in governed spend, attributed revenue, and ROI; persisted with timestamps; labeled AI-generated; and designed for human approval. The repository also includes the exact model request and real returned output.

**Technical stakeholder:** “Why not query the warehouse from the app?”  
Lakebase gives predictable operational latency and isolates customer-facing traffic from analytical compute. Warehouses remain appropriate for Genie and batch intelligence.

**Technical stakeholder:** “What happens when sync fails?”  
The job enforces dependencies, synced-table state is monitored, freshness validation fails the run, and the last successful Lakebase snapshot remains available.

---

# Production next steps

1. Replace synthetic feeds with governed production connectors.
2. Calibrate renewal health against observed renewal outcomes.
3. Add human feedback and evaluation for AI recommendations.
4. Set latency, quality, and model-output monitors with operational alerts.
5. Promote the bundle through isolated development, staging, and production targets.
