# Find the revenue at risk before the renewal conversation
## Renewal Radar: modelled churn, campaign ROI and next-best actions inside the Traackr platform

Synthetic data only · every figure below traces to a governed table in the deployed build

---

# The outcome

In the demo portfolio of 120 brands and 900 creator campaigns, the build surfaces two numbers before a renewal conversation starts:

| | Value | How it is derived |
|---|---:|---|
| **ARR in brands the model scores high-risk** | **$6.1M of $17.8M** (46 of 120 brands) | UC-registered classifier scored on governed brand features |
| **Annualised revenue from moving 30% of spend off 32 underperforming campaigns** | **$1.22M** on **$741K** trailing-90-day spend | `gold_reallocation_opportunity`: shifted spend × (regional benchmark ROI − campaign ROI) |

Both are computed in the pipeline, persisted, synced to Lakebase and served through a brand-scoped API. The first is a retention number for Traackr. The second is a performance number Traackr can put in front of its brands.

These are illustrations of the sizing method on synthetic data. The 30% shift is a planning assumption to calibrate with real outcomes, not a forecast. The synthetic churn history is deliberately high (about 40%) so the model has signal to learn, so the dollar amounts show how the number is built, not a market churn rate.

---

# The pressure on Traackr

*Positioning to validate with Traackr's team; these are not measured market statistics.*

- **Established creator-marketing platforms compete on the same workflow** (for example CreatorIQ, Aspire and GRIN), so features that look like discovery or reporting converge quickly. Differentiation shifts to what the platform *tells a brand to do next*.
- **Brands are being asked to prove creator spend,** and ask which creators and campaigns earned it. A platform that cannot answer in the same session loses the renewal to one that can.
- **Social and commerce platforms increasingly ship their own creator tooling,** which pushes independent platforms toward cross-platform, cross-channel intelligence that no single network will give a brand.
- **AI-native entrants and agentic features reset expectations.** Traackr is already moving to an agentic product with usage-based pricing, so every answer has a marginal cost and a quality bar. Grounded, cached, auditable answers matter more than demos.

What this means for the build: the product is not a dashboard. It is retention intelligence (who is about to leave and why) plus performance intelligence (where a brand should move money), delivered through the API Traackr's own portals already call.

---

# Who it is for

## Executive sponsor: Chief Customer Officer / CRO at Traackr
- Spot renewal risk while there is still time to act, with a modelled churn probability and the drivers behind it.
- Protect ARR: **$6.1M** sits in high-risk brands in the demo portfolio.
- Measured on net revenue retention and renewal rate.

## Day-to-day owners: Customer Success operations and the API platform team
- Work a ranked list of at-risk brands with a specific action per flagged campaign.
- Serve brand portals from Lakebase instead of analytical compute: **under 10 ms** measured round trip (8.9 ms).
- Measured on time-to-insight, data-freshness SLA (freshness gate passes in the orchestrated run) and API reliability.

## End users: brand marketing teams
- See their own campaigns, ROI versus regional benchmark, and a persisted AI action. A brand-scoped key can only ever see that brand.

---

# The integrated data journey

```
Synthetic CRM · billing · ad spend · social · sales · CDC feeds     (generator with executable checks)
  → Unity Catalog volume
  → Lakeflow: Auto Loader bronze → silver → gold → platinum (AUTO CDC, SCD Type 1)
  → MLflow: renewal-risk classifier registered in UC (champion alias)
  → ai_gen: campaign actions grounded in metrics AND the brand's model risk score
  → Lakebase Autoscaling synced tables
  → FastAPI on Databricks Apps  +  curated Genie space
```

One job, `radar-daily-orchestration`, enforces the order and ends in a freshness gate. A full run on the deployed workspace took **592 s** end to end, including one transient task crash that the platform retried (both attempts are in the transcript).

---

# Data engineered to carry the story

The generator is not random rows. It fails the job unless these hold, and the cluster run recorded them:

| Invariant | Recorded value |
|---|---|
| Creator tier fixes follower band | nano 1,002–9,992 · micro 10,013–99,985 · mid 100,168–999,954 · macro 1,034,841–4,956,811 |
| Seeded creator/campaign surge (`CR-00042` × `CMP-00137`) | **exactly $224,000**, and it is the top revenue pair |
| Holiday seasonality changes ROI, not just volume | NA holiday ROI **2.39** vs off-season **1.81** |
| Region-specific peaks | NA/EMEA holiday, APAC Singles' Day and Lunar New Year, LATAM Dec–Jan (**1.91**) |
| A structurally inefficient cohort exists | **14.8%** of campaigns, the source of the reallocation opportunity |
| Regional churn skew in the training labels | LATAM **53%** vs NA **38%** |

Scale: 223,851 social events, 223,907 attributed sales, 49,210 ad-spend days, 120 brands, 3,000 creators, 900 campaigns, plus ordered CDC feeds with updates and a deletion.

---

# The value, built bottom-up

Not a flat percentage. Each step is a table you can query:

1. **Find underperformers.** Campaigns active in the last 90 days with ROI below 1.0 and more than $5K spend: **32 campaigns, $740,710** trailing-90-day spend.
2. **Set a benchmark.** Median 90-day ROI of paying campaigns in the same region (about 1.8–2.2×).
3. **Move 30% of the spend,** annualised: **$888,853**.
4. **Earn the ROI gap on the moved dollars:** **$1,222,737** of additional attributed revenue per year.
5. **Retention, as a sensitivity on governed ARR:** $6.1M sits in high-risk brands. Each 10 points of that ARR retained is **$612K**.

The top gaps are named in the app, for example *Orchard Beauty Fall Push 80*: 90-day ROI 0.33 against a regional benchmark of 1.97, worth $85,955 a year if 30% of its spend moves.

---

# Intelligence users can trust

- **A trained model, not a prompt.** Gradient-boosted renewal-risk classifier trained on 540 renewal cycles, **holdout AUC 0.80**, registered in Unity Catalog (`renewal_risk`, `champion` alias). It is only promoted if it holds up against the current champion.
- **The model and the Gen AI layer work together.** The `ai_gen` prompt receives the campaign's metrics *and the brand's modelled churn probability*, so a campaign on a brand at 95% risk is handled differently from one at 5%.
- **Persisted, not generated on page open.** Actions are written in the pipeline run, synced to Lakebase and served in milliseconds. A separate route calls the foundation model on demand for an explanation, with the endpoint name, latency and token use returned.
- **Inspectable.** Genie answers analytical questions with its generated SQL. For "which API endpoint…" questions it answers from a governed catalog and shows an executable call, not SQL.
- **Labelled** "AI-generated — verify before acting."

Known weakness: for high-risk brands the generated action is still fairly generic ("prioritise retention…"). Tying it to specific creator swaps is the next improvement.

---

# Governance at the data layer and the API layer

- **Unity Catalog row-level security** on `brand_radar` and `campaign_actions` (`brand_row_filter`, backed by a `brand_access` grants table), so brand isolation holds for SQL, Genie and notebooks, not only the API.
- **Platform constraint found and designed around:** Lakebase cannot sync from a row-filtered table, so the sync reads unfiltered `*_serving` copies that only the pipeline owner can read.
- **Scoped API keys:** `portfolio` and `brand`. A brand key asking for another brand gets **404** (never 403, so keys cannot probe which brands exist); a brand key on a portfolio route gets **403**.
- Quality expectations drop bad rows at bronze; table comments throughout; every task writes to a `run_log` table and every request to a Lakebase `request_log`.

---

# Decisions and trade-offs

| Decision | Why | Trade-off |
|---|---|---|
| Serve the API from Lakebase Autoscaling | Predictable operational latency; no warehouse wake-up | Needs lakehouse-to-Lakebase sync and a freshness gate |
| Persist `ai_gen` output | Auditable and stable; no inference on page open | Refreshes per orchestration run, not continuously |
| Train and register a model | A trained score the Gen AI layer can use, with lineage | Demonstrates the pattern on synthetic labels, not a validated production model |
| Unfiltered serving copies | The platform cannot sync a row-filtered table | One more copy to refresh, owner-only |
| Synthetic data | Safe and reproducible | Value estimates need production calibration |

---

# AI as a force multiplier

This repository is a **rebuild**. An earlier version was started from a scaffold generator and was returned with the instruction to rebuild it as original work. This one shares no code with it. The agent worked as a reviewer that had to prove each claim against the live workspace, and it changed the design:

- The seeded-region churn assertion **failed on the cluster** (too few LATAM accounts for a small effect). It led to a larger effect, more renewal cycles, and running the whole check suite locally before spending more cluster time.
- Scoring flagged **96 of 120 brands as high risk.** The agent traced it to a train/serve mismatch (active campaigns 3.9 vs 0.8, revenue trend 0.04 vs 0.94). The features were bounded and aligned, and high risk fell to **46**.
- Row-level security was rejected by the platform for synced sources, which produced the serving-copy design.
- Four smaller defects the agent found only by running: a sync wait loop that would never exit, a naive-vs-aware timestamp crash in the freshness gate, an empty AI-actions page, and a model response returned as raw reasoning blocks.

Every correction is in `docs/AI_BUILD_LOG.md`. The business framing, the customer choice and the decision to rebuild were the owner's, not the agent's.

---

# Evidence, not architecture claims

`evidence/RAW_EXECUTION_TRANSCRIPT.md` is produced by `scripts/capture_evidence.py`, which queries the workspace and the deployed app at capture time. It contains:

- Run `330757386726266` with every task, attempt, duration and dependency (including the failed first freshness attempt and its successful retry)
- The generator's recorded story checks, model AUC and registered version, and the freshness result for every mirror
- Row counts per governed table, risk bands, the bottom-up value table, regional seasonality, and real `ai_gen` rows
- The UC row filter from `DESCRIBE EXTENDED`
- Live API responses, including the 404 and 403 scoping cases, a live model explanation with token usage, and two Genie conversations with their IDs
- The Lakebase request log of the calls above

---

# Live roleplay: tell — show — tell

## Tell (30 seconds)
"A creator-marketing platform has renewals coming and no early signal for which brands are at risk, or which of their campaigns are wasting budget. In this demo portfolio, $6.1M of ARR sits in brands our model flags high-risk, and moving 30% of spend off 32 underperforming campaigns is worth about $1.2M a year to the brands. All of it comes from governed data and is served through the API your portals already use."

## Show (3 minutes)
1. Open on the outcome page: the two numbers and ROI by region.
2. Open Renewal risk: brands ranked by modelled churn probability.
3. Open AI actions: pick *Orchard Beauty Fall Push 80*, read the action, and click "Explain with live model".
4. Ask Genie "Which API endpoint shows renewal risk?" and show the call and the conversation link.
5. Ask "Which region has the lowest ROI?" and show the generated SQL.
6. Switch the viewer to Saffron Beauty: the overview, risk drivers and actions become that brand's, its Genie questions are logged under its own view, and another brand returns 404.

## Tell (30 seconds)
"One governed pipeline takes raw feeds to a risk score and an action, serves it in single-digit milliseconds, and keeps each brand's data isolated at both the API and the table."

---

# Objections to rehearse

**Is the $1.2M guaranteed?** No. It assumes 30% of an underperformer's spend can move to the regional benchmark and earn that ROI. It sizes the opportunity from real rows so the assumption can be tested and replaced with observed results.

**Why trust the churn model?** It is trained on governed history, scored against a held-out set (AUC 0.80), and only promoted if it holds up. It is a demonstration of the pattern on synthetic labels; production needs Traackr's real renewal outcomes.

**Why not query the warehouse from the app?** Lakebase gives predictable latency for customer-facing traffic and isolates it from analytical compute. The warehouse stays for Genie and batch work.

**What happens if the sync fails?** The job fails at the freshness gate, and the last synced snapshot stays in Lakebase.

**Won't the AI text be wrong sometimes?** It is grounded in a few governed numbers, persisted and labelled. The next step is evaluation against analyst judgement.

---

# Production next steps

1. Replace synthetic feeds with governed connectors and Traackr's real renewal history.
2. Calibrate the risk model and the 30% reallocation assumption against observed outcomes.
3. Make AI actions concrete (specific creator and budget moves) and evaluate them against analyst judgement.
4. Add monitors and alerts on freshness, model drift and request latency.
5. Promote the bundle through isolated dev, staging and production targets.
