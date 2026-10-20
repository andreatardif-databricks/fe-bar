# FE Bar Submission Answers

## Customer name

Traackr

## Industry / vertical

Influencer marketing technology / marketing technology for global consumer brands

## What is the business challenge you are solving?

Global consumer brands using Traackr struggle to connect creator activity and campaign spend with attributed revenue, campaign ROI, and account-renewal risk quickly enough to act. The underlying data is fragmented across CRM, social, advertising, contract, and billing systems. Analysts must manually reconcile those sources, operational portals lag the analytical lakehouse, and campaign managers receive recommendations too late to reallocate budget or protect at-risk renewals.

This prototype addresses a specific decision: which campaigns and creators should a brand fund, pause, or investigate now to improve influencer-marketing return and reduce renewal risk?

## How does your Databricks solution address this challenge?

The solution implements one integrated, governed data journey rather than separate product demos:

1. Synthetic CRM, social, advertising, contract, billing, creator, and campaign data lands as raw files in Unity Catalog Volumes.
2. A serverless Lakeflow Spark Declarative Pipeline incrementally processes the raw data through Bronze streaming tables, Silver and Gold materialized views, and Platinum serving tables.
3. Unity Catalog governs the volumes, tables, schemas, lineage, comments, permissions, constraints, and reusable business metrics throughout the journey.
4. Databricks `ai_gen` evaluates governed campaign performance and persists grounded campaign recommendations. Inference runs during the orchestrated refresh, not when a user opens the app.
5. The curated Platinum tables and persisted AI recommendations synchronize into Lakebase. Lakebase provides low-latency operational serving for the application and customer-facing APIs without waking a SQL warehouse on every page load.
6. A FastAPI Databricks App surfaces renewal health, campaign and creator performance, AI recommendations, API-key administration, an API playground, architecture source, and a live raw-event-to-API propagation demonstration.
7. A curated Traackr Genie Agent makes the governed analytical data queryable in natural language. Business questions return inspectable generated SQL, while API-help questions return executable API scripts and a direct link to the Genie conversation.

Lakeflow Jobs enforce the dependency chain: pipeline processing succeeds before GenAI enrichment, GenAI succeeds before Lakebase synchronization, and freshness validation succeeds before the run is considered complete. The final clean orchestration run completed all five tasks, and the measured raw-event-to-API journey was 4 minutes 22 seconds.

## What AI tools did you use, and what was your workflow? What decisions and trade-offs did you have to make?

I used a Databricks coding agent as an engineering teammate for rubric-gap analysis, solution design, code generation and review, deployment automation, runtime diagnosis, performance testing, execution-evidence capture, and role-play preparation. I also used Databricks `ai_gen` inside the data pipeline to create persisted campaign recommendations and a curated Genie Agent for governed natural-language analytics and API guidance.

My workflow was iterative: define the customer decision and acceptance criteria; generate only synthetic data; implement each platform stage; deploy through a Databricks Asset Bundle; run the full orchestration; inspect job, pipeline, Lakebase, app, and Genie outputs; diagnose failures and latency; capture readable evidence; and refine the business narrative and demo based on the FE Bar rubric. I used the AI agent to challenge architecture claims and verify them with live endpoint timings, pipeline states, synced-table results, generated SQL, API scripts, and application logs rather than accepting source code as proof.

Key decisions and trade-offs:

- Persist GenAI output during orchestration instead of generating it on page load. This improves latency, repeatability, auditability, and cost control, but recommendations update on the governed refresh cadence rather than continuously.
- Serve operational application data from Lakebase instead of a SQL warehouse. This provides predictable, sub-second operational reads and isolates portal traffic from analytical compute, but requires an explicit and monitored lakehouse-to-Lakebase synchronization step.
- Keep Genie on curated Unity Catalog tables. This provides governed natural-language analysis and inspectable SQL, while accepting that Genie analytical execution uses a SQL warehouse rather than Lakebase.
- Use synthetic data instead of customer data. This makes the repository safe and reproducible, but production value estimates and model behavior require calibration with approved customer data.
- Use a server-rendered FastAPI application with lightweight JavaScript. This kept the prototype achievable within the FE Bar time box and made the source easy to review, while providing fewer abstractions than a larger frontend framework.

## What are the business outcomes and impact?

The prototype changes the operating model from next-day manual analysis to a governed, operational decision product:

- A measured 4 minutes 22 seconds from a new synthetic source event to a confirmed customer-facing API response.
- Low-latency Lakebase-backed application and API reads without running GenAI inference or waking a SQL warehouse whenever the app opens.
- Persisted, traceable recommendations that tell campaign managers which campaigns to fund, pause, or investigate.
- One consistent governed data foundation for developers, campaign managers, analysts, and account teams through APIs, the Databricks App, and Genie.
- Faster identification of weak campaign ROI and renewal risk, reducing manual reconciliation and shortening time to action.

For an illustrative global consumer brand spending $10 million annually on influencer marketing, redirecting 2% of inefficient investment represents $200,000 in annual value protection. This is an explicit scenario-based estimate, not a guaranteed result; production deployment would calibrate the assumption against the customer's baseline spend, conversion attribution, analyst effort, and renewal performance.

## GitHub repo link

https://github.com/andreatardif-databricks/fe-bar

## Presentation deck

`presentation/traackr_fe_bar_deck.md`

## Local repository folder

`/Users/andrea.tardif/Desktop/influencer-engagement-fe-bar`

## Optional AI conversation IDs

- Initial build: `01a11d83-260a-7802-9307-20ca1bffeba5`
- Continuation: `01a155d4-10d6-7672-a6c2-231612719886`
