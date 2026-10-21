# Databricks notebook source
# MAGIC %md
# MAGIC # Renewal Radar: synthetic source generator
# MAGIC
# MAGIC Writes raw parquet drops into a Unity Catalog volume. Every job run lands a new batch
# MAGIC (`batch=<run_ts>`) so Auto Loader sees genuine increments. The first run backfills
# MAGIC 18 months of history; later runs append the newest days plus ordered CDC changes.
# MAGIC
# MAGIC The data is built to carry the business story, and the job fails if the story drifts:
# MAGIC creator tier fixes the follower band, holiday and regional seasonality changes spend and
# MAGIC revenue differently per region, a low-efficiency campaign cohort drives the
# MAGIC reallocation opportunity, and one creator/campaign pair carries a seeded surge whose
# MAGIC total is asserted to the dollar.

# COMMAND ----------

dbutils.widgets.text("catalog", "at_workspace_102126")
dbutils.widgets.text("schema", "renewal_radar")
CATALOG = dbutils.widgets.get("catalog")
SCHEMA = dbutils.widgets.get("schema")
LANDING = f"/Volumes/{CATALOG}/{SCHEMA}/landing"

def record_run(task: str, payload: dict) -> None:
    """Persist this task's result to the governed run_log table and return it as the task exit value."""
    import json as _json
    from datetime import datetime as _dt, timezone as _tz
    body = _json.dumps(payload, sort_keys=True, default=str)
    spark.createDataFrame([(task, _dt.now(_tz.utc).isoformat(), body)], "task STRING, recorded_at STRING, payload STRING") \
        .write.mode("append").saveAsTable(f"{CATALOG}.{SCHEMA}.run_log")
    dbutils.notebook.exit(body)

# COMMAND ----------

import json
import zlib
from datetime import date, datetime, timedelta, timezone

import numpy as np
import pandas as pd

SEED = 20261020
rng = np.random.default_rng(SEED)

TODAY = date.today()
HISTORY_DAYS = 540
RUN_TS = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")

REGIONS = {"NA": ["US", "CA"], "EMEA": ["UK", "FR", "DE", "AE"], "APAC": ["JP", "KR", "AU", "SG"], "LATAM": ["BR", "MX"]}
REGION_WEIGHTS = {"NA": 0.38, "EMEA": 0.30, "APAC": 0.20, "LATAM": 0.12}
INDUSTRIES = ["beauty", "fashion", "fitness", "food_beverage", "consumer_tech", "travel"]

# creator tier -> (follower floor, follower ceiling, base engagement rate)
TIER_BANDS = {
    "nano": (1_000, 10_000, 0.060),
    "micro": (10_000, 100_000, 0.040),
    "mid": (100_000, 1_000_000, 0.025),
    "macro": (1_000_000, 5_000_000, 0.015),
}
# account tier -> (ARR floor, ARR ceiling)
ACCOUNT_BANDS = {"enterprise": (250_000, 600_000), "growth": (80_000, 250_000), "starter": (20_000, 80_000)}

HEADLINE_CREATOR = "CR-00042"
HEADLINE_CAMPAIGN = "CMP-00137"
SURGE_DAYS = 56
SURGE_DAILY_USD = 4_000.0
SURGE_TOTAL_USD = SURGE_DAYS * SURGE_DAILY_USD  # 224,000 exactly

# COMMAND ----------

def season_multipliers(day: date, region: str) -> tuple[float, float]:
    """Return (spend multiplier, revenue multiplier) for a region on a calendar day.

    Spend rises into a regional peak; revenue rises faster, so ROI itself is seasonal.
    """
    m, d = day.month, day.day
    spend, revenue = 1.0, 1.0
    if region in ("NA", "EMEA") and m in (11, 12):
        spend, revenue = 1.25, 1.55          # holiday gifting
    if region == "APAC" and ((m == 11 and 5 <= d <= 14) or (m == 2 and d <= 14)):
        spend, revenue = 1.30, 1.75          # Singles' Day and Lunar New Year
    if region == "LATAM" and (m == 12 or (m == 1 and d <= 10)):
        spend, revenue = 1.20, 1.45          # summer-season peak
    return spend, revenue


def lpad(prefix: str, n: int, width: int) -> str:
    return f"{prefix}-{n:0{width}d}"


def exists(path: str) -> bool:
    try:
        dbutils.fs.ls(path)
        return True
    except Exception:
        return False


FIRST_RUN = not exists(f"{LANDING}/accounts")
print(f"RUN_TS={RUN_TS} FIRST_RUN={FIRST_RUN}")

# COMMAND ----------
# MAGIC %md ## 1. Reference entities (stable across runs, regenerated deterministically)

# COMMAND ----------

N_ACCOUNTS, N_CREATORS, N_CAMPAIGNS = 120, 3000, 900

acc_tier = rng.choice(list(ACCOUNT_BANDS), size=N_ACCOUNTS, p=[0.15, 0.35, 0.50])
acc_region = rng.choice(list(REGION_WEIGHTS), size=N_ACCOUNTS, p=list(REGION_WEIGHTS.values()))
acc_arr = np.array([rng.uniform(*ACCOUNT_BANDS[t]) for t in acc_tier]).round(-2)

_pre = ["Aster", "Brindle", "Calloway", "Dovetail", "Elmwood", "Fernhill", "Garnet", "Halcyon", "Indigo", "Juniper",
        "Kestrel", "Lumina", "Marlowe", "Nettle", "Orchard", "Prism", "Quill", "Riverstone", "Saffron", "Tamarack"]
_suf = ["Lane", "& Co", "Beauty", "Athletics", "Provisions", "Outfitters", "Labs", "Collective"]

accounts = pd.DataFrame({
    "account_id": [lpad("ACC", i, 4) for i in range(N_ACCOUNTS)],
    "brand_name": [f"{_pre[i % len(_pre)]} {_suf[(i * 7) % len(_suf)]}" for i in range(N_ACCOUNTS)],
    "industry": rng.choice(INDUSTRIES, size=N_ACCOUNTS),
    "region": acc_region,
    "tier": acc_tier,
    "arr_usd": acc_arr,
})
accounts["country"] = [rng.choice(REGIONS[r]) for r in accounts["region"]]
accounts["renewal_date"] = [TODAY + timedelta(days=int(x)) for x in rng.integers(10, 200, N_ACCOUNTS)]
accounts["owner_email"] = [f"csm{i % 14}@traackr-demo.example" for i in range(N_ACCOUNTS)]
# latent health trait drives ROI, activity and renewal outcomes downstream
accounts["trait"] = rng.normal(0, 1, N_ACCOUNTS)

tier_c = rng.choice(list(TIER_BANDS), size=N_CREATORS, p=[0.50, 0.30, 0.15, 0.05])
creators = pd.DataFrame({
    "creator_id": [lpad("CR", i, 5) for i in range(N_CREATORS)],
    "tier": tier_c,
    "platform": rng.choice(["tiktok", "instagram", "youtube"], size=N_CREATORS, p=[0.55, 0.33, 0.12]),
    "region": rng.choice(list(REGION_WEIGHTS), size=N_CREATORS, p=list(REGION_WEIGHTS.values())),
})
creators["follower_count"] = [int(rng.uniform(*TIER_BANDS[t][:2])) for t in creators["tier"]]
creators["handle"] = [f"@creator{i:05d}" for i in range(N_CREATORS)]
creators["status"] = rng.choice(["active", "paused", "under_review"], size=N_CREATORS, p=[0.82, 0.12, 0.06])
creators.loc[creators.creator_id == HEADLINE_CREATOR, ["tier", "follower_count", "platform", "region", "status"]] = \
    ["macro", 2_400_000, "tiktok", "NA", "active"]

# campaigns start over the whole history; seasonality is applied when daily facts are built
camp_start_off = rng.integers(0, HISTORY_DAYS - 20, N_CAMPAIGNS)
camp_len = rng.integers(21, 90, N_CAMPAIGNS)
camp_acct = rng.integers(0, N_ACCOUNTS, N_CAMPAIGNS)
# enterprise brands run more campaigns
camp_acct = np.where(rng.random(N_CAMPAIGNS) < 0.35, rng.choice(np.where(acc_tier == "enterprise")[0], N_CAMPAIGNS), camp_acct)

campaigns = pd.DataFrame({
    "campaign_id": [lpad("CMP", i, 5) for i in range(N_CAMPAIGNS)],
    "account_id": [accounts.account_id[i] for i in camp_acct],
    "start_date": [TODAY - timedelta(days=HISTORY_DAYS - int(o)) for o in camp_start_off],
})
campaigns["end_date"] = [s + timedelta(days=int(l)) for s, l in zip(campaigns.start_date, camp_len)]
campaigns["region"] = [accounts.region[i] for i in camp_acct]
campaigns["budget_usd"] = [float(np.round(rng.lognormal(10.2, 0.5), -2)) for _ in range(N_CAMPAIGNS)]
campaigns["name"] = [f"{accounts.brand_name[i]} {['Spring', 'Summer', 'Fall', 'Holiday'][(s.month % 12) // 3]} Push {n}"
                     for n, (i, s) in enumerate(zip(camp_acct, campaigns.start_date))]
# a fixed cohort (14%) is structurally inefficient; brand trait shifts efficiency for everyone else
campaigns["eff_factor"] = np.where(rng.random(N_CAMPAIGNS) < 0.14, rng.uniform(0.35, 0.85, N_CAMPAIGNS),
                             np.exp(rng.normal(0.65, 0.35, N_CAMPAIGNS)))
campaigns["eff_factor"] *= np.exp(0.12 * accounts.trait.values[camp_acct])

# pin the headline campaign
h = campaigns.campaign_id == HEADLINE_CAMPAIGN
campaigns.loc[h, ["account_id", "region", "start_date", "end_date", "budget_usd", "name", "eff_factor"]] = [
    accounts.account_id[0], "NA", TODAY - timedelta(days=120), TODAY - timedelta(days=1), 400_000.0,
    "Aster Lane Holiday Glow", 1.4]
accounts.loc[0, ["region", "tier", "country"]] = ["NA", "enterprise", "US"]
accounts.loc[0, "arr_usd"] = 480_000.0

campaigns["status"] = np.where(campaigns.end_date < TODAY - timedelta(days=3), "ended",
                         np.where(campaigns.start_date > TODAY, "scheduled", "active"))

# COMMAND ----------
# MAGIC %md ## 2. Daily facts: ad spend, social engagement, attributed sales

# COMMAND ----------

def build_daily(window_start: date, window_end: date):
    spend_rows, social_rows, sales_rows = [], [], []
    creator_lookup = creators.set_index("creator_id")[["tier", "follower_count"]].to_dict("index")
    for c in campaigns.itertuples():
        lo, hi = max(c.start_date, window_start), min(c.end_date, window_end)
        if lo > hi:
            continue
        n_days = (c.end_date - c.start_date).days or 1
        creator_pool = creators[(creators.region == c.region) & (creators.status != "under_review")]
        k = int(rng.integers(3, 7))
        crew = creator_pool.sample(k, random_state=zlib.crc32(c.campaign_id.encode())).creator_id.tolist()
        if c.campaign_id == HEADLINE_CAMPAIGN and HEADLINE_CREATOR not in crew:
            crew[0] = HEADLINE_CREATOR
        for offset in range((hi - lo).days + 1):
            day = lo + timedelta(days=offset)
            sp_mult, rev_mult = season_multipliers(day, c.region)
            daily_spend = c.budget_usd / n_days * sp_mult * rng.uniform(0.8, 1.2)
            spend_rows.append((f"SP-{c.campaign_id}-{day:%Y%m%d}", c.campaign_id, day, round(daily_spend, 2),
                               int(daily_spend * rng.uniform(7, 11))))
            for cr in crew:
                crow = creator_lookup[cr]
                impressions = int(rng.lognormal(9.5, 0.4) * (1 + np.log10(crow["follower_count"])) / 3)
                eng_rate = TIER_BANDS[crow["tier"]][2] * rng.uniform(0.7, 1.3)
                engagements = int(impressions * eng_rate)
                social_rows.append((f"SO-{c.campaign_id}-{cr}-{day:%Y%m%d}", c.campaign_id, cr, day, impressions, engagements))
                revenue = daily_spend / k * c.eff_factor * rev_mult * rng.uniform(0.7, 1.3)
                sales_rows.append((f"SA-{c.campaign_id}-{cr}-{day:%Y%m%d}", c.campaign_id, cr, day, round(revenue, 2), "paid"))
    return spend_rows, social_rows, sales_rows


if FIRST_RUN:
    w_start, w_end = TODAY - timedelta(days=HISTORY_DAYS), TODAY
else:
    w_start, w_end = TODAY - timedelta(days=2), TODAY

spend_rows, social_rows, sales_rows = build_daily(w_start, w_end)
ad_spend = pd.DataFrame(spend_rows, columns=["spend_id", "campaign_id", "spend_date", "spend_usd", "clicks"])
social = pd.DataFrame(social_rows, columns=["event_id", "campaign_id", "creator_id", "event_date", "impressions", "engagements"])
sales = pd.DataFrame(sales_rows, columns=["sale_id", "campaign_id", "creator_id", "sale_date", "revenue_usd", "payment_status"])

# seeded surge: only on the first (backfill) run so the asserted total is stable
if FIRST_RUN:
    surge_days = [TODAY - timedelta(days=SURGE_DAYS - i) for i in range(SURGE_DAYS)]
    surge = pd.DataFrame({
        "sale_id": [f"SA-SURGE-{d:%Y%m%d}" for d in surge_days],
        "campaign_id": HEADLINE_CAMPAIGN, "creator_id": HEADLINE_CREATOR, "sale_date": surge_days,
        "revenue_usd": SURGE_DAILY_USD, "payment_status": "paid"})
    sales = pd.concat([sales, surge], ignore_index=True)

# a small share of refunds exercises the quality filters downstream (never the seeded surge)
refundable = sales.index[~sales.sale_id.str.startswith("SA-SURGE")]
sales.loc[rng.choice(refundable, size=int(len(refundable) * 0.02), replace=False), "payment_status"] = "refunded"

# COMMAND ----------
# MAGIC %md ## 3. Billing, renewal history (model training labels), and CDC feeds

# COMMAND ----------

inv_rows = []
for a in accounts.itertuples():
    months = 18 if FIRST_RUN else 1
    for m in range(months):
        due = TODAY - timedelta(days=30 * (months - 1 - m))
        late_p = float(1 / (1 + np.exp(1.2 * a.trait + 1.8)))
        late = rng.random() < late_p
        inv_rows.append((f"INV-{a.account_id}-{due:%Y%m}", a.account_id, due, round(a.arr_usd / 12, 2),
                         "paid_late" if late else "paid", int(rng.integers(8, 40)) if late else 0))
invoices = pd.DataFrame(inv_rows, columns=["invoice_id", "account_id", "due_date", "amount_usd", "status", "days_late"])

# prior renewal cycles with outcomes. Outcome depends on the same latent traits the facts use,
# plus regional and tier effects, so a model trained on this table recovers the story.
hist = []
region_shift = {"NA": 0.0, "EMEA": 0.10, "APAC": -0.15, "LATAM": 1.10}
tier_shift = {"enterprise": -0.4, "growth": 0.0, "starter": 0.5}
for a in accounts.itertuples():
    for cycle in range(1, 7):
        t = a.trait + rng.normal(0, 0.45)
        avg_roi = float(np.clip(1.4 + 0.40 * t + rng.normal(0, 0.20), 0.3, 4.0))
        active = int(np.clip(round(2.5 + 1.0 * t + rng.normal(0, 0.8)), 0, 10))
        trend = float(np.clip(0.04 + 0.12 * t + rng.normal(0, 0.08), -0.5, 0.6))
        late_rate = float(np.clip(0.18 - 0.07 * t + rng.normal(0, 0.04), 0, 0.8))
        logit = -1.5 - 1.4 * (avg_roi - 1.4) - 0.25 * (active - 2.5) - 2.2 * trend + 4.0 * late_rate \
                + region_shift[a.region] + tier_shift[a.tier]
        churned = bool(rng.random() < 1 / (1 + np.exp(-logit)))
        hist.append((f"{a.account_id}-C{cycle}", a.account_id, cycle, a.region, a.tier,
                     round(avg_roi, 4), active, round(trend, 4), round(late_rate, 4), churned))
renewal_history = pd.DataFrame(hist, columns=["cycle_id", "account_id", "cycle", "region", "tier", "avg_roi_180d",
                                              "active_campaigns", "revenue_trend_90d", "late_invoice_rate", "churned"])

seq_base = int(datetime.now(timezone.utc).timestamp())
creator_cdc, campaign_cdc = [], []
if FIRST_RUN:
    for i, r in enumerate(creators.itertuples()):
        creator_cdc.append((f"CC-{i}-1", r.creator_id, "INSERT", seq_base + i, r.handle, r.tier, r.platform, r.region,
                            int(r.follower_count), r.status))
    for i, r in enumerate(campaigns.itertuples()):
        campaign_cdc.append((f"CK-{i}-1", r.campaign_id, "INSERT", seq_base + i, r.account_id, r.name, r.region, r.start_date,
                             r.end_date, float(r.budget_usd), r.status))
# every run: ordered updates (follower growth, pauses, budget revisions, one offboarding delete)
upd = creators.sample(60, random_state=int(seq_base % 9999))
for j, r in enumerate(upd.itertuples()):
    grown = int(min(r.follower_count * rng.uniform(1.01, 1.08), TIER_BANDS[r.tier][1] - 1))
    status = "paused" if j % 7 == 0 else r.status
    creator_cdc.append((f"CC-{RUN_TS}-{j}", r.creator_id, "UPDATE", seq_base + 100_000 + j, r.handle, r.tier, r.platform,
                        r.region, grown, status))
off = creators.sample(1, random_state=5).iloc[0]
creator_cdc.append((f"CC-{RUN_TS}-del", off.creator_id, "DELETE", seq_base + 200_000, off.handle, off.tier, off.platform,
                    off.region, int(off.follower_count), "offboarded"))
for j, r in enumerate(campaigns[campaigns.status == "active"].sample(25, random_state=int(seq_base % 7919)).itertuples()):
    campaign_cdc.append((f"CK-{RUN_TS}-{j}", r.campaign_id, "UPDATE", seq_base + 100_000 + j, r.account_id, r.name, r.region,
                         r.start_date, r.end_date, float(r.budget_usd) * 1.1, r.status))

creator_cdc = pd.DataFrame(creator_cdc, columns=["event_id", "creator_id", "op", "seq", "handle", "tier", "platform", "region",
                                                 "follower_count", "status"])
campaign_cdc = pd.DataFrame(campaign_cdc, columns=["event_id", "campaign_id", "op", "seq", "account_id", "name", "region",
                                                   "start_date", "end_date", "budget_usd", "status"])

# COMMAND ----------
# MAGIC %md ## 4. Executable story checks: the job fails if the data drifts from the narrative

# COMMAND ----------

checks = {}

# (a) creator tier fixes the follower band, with no exceptions
bad = [t for t in TIER_BANDS
       if not creators[creators.tier == t].follower_count.between(*TIER_BANDS[t][:2]).all()]
assert not bad, f"follower bands violated for tiers {bad}"
checks["follower_bands"] = {t: [int(creators[creators.tier == t].follower_count.min()),
                                int(creators[creators.tier == t].follower_count.max())] for t in TIER_BANDS}

# (b) account ARR respects its tier band, and enterprise ARR dominates
for t, (lo, hi) in ACCOUNT_BANDS.items():
    sub = accounts[(accounts.tier == t) & (accounts.account_id != accounts.account_id[0])]
    assert sub.arr_usd.between(lo, hi).all(), f"ARR band violated for {t}"
checks["enterprise_mean_arr_usd"] = float(accounts[accounts.tier == "enterprise"].arr_usd.mean())

if FIRST_RUN:
    # (c) the seeded surge totals exactly SURGE_TOTAL_USD
    seeded = sales[sales.sale_id.str.startswith("SA-SURGE")].revenue_usd.sum()
    assert seeded == SURGE_TOTAL_USD, f"surge total {seeded} != {SURGE_TOTAL_USD}"
    checks["seeded_surge_usd"] = float(seeded)

    # (d) the headline pair is the top creator-campaign revenue pair
    pair = sales[sales.payment_status == "paid"].groupby(["campaign_id", "creator_id"]).revenue_usd.sum().sort_values()
    assert pair.index[-1] == (HEADLINE_CAMPAIGN, HEADLINE_CREATOR), f"headline pair is {pair.index[-1]}"
    checks["headline_pair_revenue_usd"] = float(pair.iloc[-1])

    # (e) seasonality: holiday NA ROI exceeds off-season NA ROI; APAC peaks around Singles' Day and LNY
    cs = sales[sales.payment_status == "paid"].merge(campaigns[["campaign_id", "region"]], on="campaign_id")
    cs["m"] = pd.to_datetime(cs.sale_date).dt.month
    sp = ad_spend.merge(campaigns[["campaign_id", "region"]], on="campaign_id")
    sp["m"] = pd.to_datetime(sp.spend_date).dt.month

    def roi(region, months):
        r = cs[(cs.region == region) & cs.m.isin(months)].revenue_usd.sum()
        s = sp[(sp.region == region) & sp.m.isin(months)].spend_usd.sum()
        return r / s if s else float("nan")

    na_holiday, na_other = roi("NA", [11, 12]), roi("NA", [3, 4, 5, 6, 7, 8, 9])
    assert na_holiday > na_other * 1.1, f"NA holiday ROI {na_holiday:.2f} vs off-season {na_other:.2f}"
    checks["na_holiday_vs_offseason_roi"] = [round(na_holiday, 3), round(na_other, 3)]
    checks["latam_dec_jan_roi"] = round(roi("LATAM", [12, 1]), 3)

    # (f) the structurally inefficient cohort exists and is not a rounding error
    cohort = (campaigns.eff_factor < 0.9).mean()
    assert 0.10 <= cohort <= 0.30, f"inefficient cohort share {cohort:.2%}"
    checks["inefficient_campaign_share"] = round(float(cohort), 3)

    # (g) regional churn skew is present in the training labels (LATAM > NA)
    churn = renewal_history.groupby("region").churned.mean()
    assert churn["LATAM"] > churn["NA"], f"LATAM churn {churn['LATAM']:.2f} <= NA {churn['NA']:.2f}"
    checks["churn_rate_by_region"] = {k: round(float(v), 3) for k, v in churn.items()}

print("CORRELATION_CHECKS PASS " + json.dumps(checks, sort_keys=True))

# COMMAND ----------
# MAGIC %md ## 5. Land the batch

# COMMAND ----------

def land(df: pd.DataFrame, name: str, first_only: bool = False):
    if first_only and not FIRST_RUN:
        return
    out = f"{LANDING}/{name}/batch={RUN_TS}"
    sdf = spark.createDataFrame(df.drop(columns=[c for c in ("eff_factor", "trait") if c in df.columns]))
    sdf.coalesce(1).write.mode("overwrite").parquet(out)
    print(f"landed {name:<16} rows={len(df):>8,}  -> {out}")


land(accounts, "accounts", first_only=True)
land(invoices, "invoices")
land(ad_spend, "ad_spend")
land(social, "social_events")
land(sales, "creator_sales")
land(renewal_history, "renewal_history", first_only=True)
land(creator_cdc, "creator_cdc")
land(campaign_cdc, "campaign_cdc")

# COMMAND ----------

record_run("generate_sources", {"first_run": FIRST_RUN, "run_ts": RUN_TS, "checks": checks, "rows": {"accounts": len(accounts), "creators": len(creators), "campaigns": len(campaigns), "ad_spend": len(ad_spend), "social_events": len(social), "creator_sales": len(sales), "invoices": len(invoices), "renewal_history": len(renewal_history), "creator_cdc": len(creator_cdc), "campaign_cdc": len(campaign_cdc)}})
