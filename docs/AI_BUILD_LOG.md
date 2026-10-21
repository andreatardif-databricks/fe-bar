# How AI changed the shape of this build

This repository is a rebuild. An earlier version of this project (`influencer-engagement-fe-bar`)
was started from a scaffold generator and was returned by the FE Bar with the instruction to rebuild
it as original work. This repo shares no code with it. The earlier project was used only as a
reference for SDK behaviour (Lakebase synced-table and OAuth calls), and its design was changed where
review showed it was weak.

The coding agent worked as a reviewer that had to prove each claim against the live workspace. The
table records the places where that changed the design or caught a defect, in the order they happened.

| What the agent proposed or I built first | What live evidence showed | What changed |
|---|---|---|
| Generator checks written as assertions | First cluster run failed on a pandas `itertuples` renaming bug in my own code | Renamed the latent columns; reran |
| Region churn skew set to a mild effect | The `LATAM churn > NA churn` assertion **failed on the cluster**: only ~14 LATAM accounts, so noise swamped a small effect | Raised the effect size, widened history to 6 renewal cycles, and ran the whole check suite locally before spending another cluster run |
| Model trained on history generated around a convenient centre | Scoring flagged **96 of 120 brands as high risk**. Feature means differed sharply between training and serving (active campaigns 3.9 vs 0.8, revenue trend 0.04 vs 0.94) | Bounded the trend feature, used one 90-day activity window in both places, re-centred the generated history on the served distribution, and re-baselined with a full refresh. High risk fell to 46 of 120 |
| Row-level security applied to the tables Lakebase syncs from | The platform rejected it: `cannot have both row/column security and online materialized views` | Split the design: sync reads unfiltered `*_serving` copies, owner-only; every analyst-facing table keeps its UC row filter |
| Sync wait loop compared state to `ONLINE_NO_PENDING_UPDATE` | The API returns `SYNCED_TABLE_ONLINE_NO_PENDING_UPDATE`; the loop would have run to its 40-minute timeout on healthy tables | Compare with `endswith` |
| Freshness gate subtracted two timestamps | Spark returns naive timestamps and Postgres aware ones, so the gate crashed after the three count checks passed | Normalised both sides to UTC |
| Portfolio console reused a per-brand route | The demo brand had no flagged campaigns, so the AI-actions page rendered empty | Added `GET /v1/portfolio/actions` |
| Model explanation returned `choices[0].message.content` directly | The foundation model returns typed blocks (reasoning plus text); the API returned the raw list | Extract visible text only |

## Working pattern

State a measurable requirement, run it against the deployed workspace, read the actual failure,
change one boundary, and keep the raw output. Suggestions were kept only after live verification.

## What the agent did not decide

The business framing, the choice of Traackr as the customer, the demo's scope, and the decision to
rebuild instead of patch were made by the project owner. Market and competitive statements in the deck
are positioning to validate with the customer, not measured facts.
