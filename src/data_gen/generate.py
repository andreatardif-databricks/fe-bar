# Databricks notebook source
"""
Synthetic data generator for the Traackr Influencer Revenue Pipeline demo.
See PROJECT/specifications/01-lakeflow.md (Section A) for the contract.

Outputs parquet under:
  /Volumes/ai_demo_gen/dev_andrea_tardif_demo_influencer_revenue_pipeline_modernized/raw_data/<source>/
  /Volumes/ai_demo_gen/dev_andrea_tardif_demo_influencer_revenue_pipeline_modernized/cdc_events/{creators,campaigns}/
"""
from databricks.connect import DatabricksSession
from pyspark.sql import functions as F
from pyspark.sql.types import StringType
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

CATALOG = "at_10526_workspace"
SCHEMA = "influencer_engagement_fe_bar"
RAW = f"/Volumes/{CATALOG}/{SCHEMA}/raw_data"
CDC = f"/Volumes/{CATALOG}/{SCHEMA}/cdc_events"

# Time anchors
NOW = datetime.utcnow()
STORY_END = NOW
STORY_START = NOW - timedelta(days=540)  # 18 months
SURGE_PEAK = NOW - timedelta(weeks=3)
RENEWAL_START = NOW + timedelta(days=7)

spark = DatabricksSession.builder.serverless(True).getOrCreate()
spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"USE SCHEMA {SCHEMA}")

print(f"NOW={NOW.isoformat()}  SURGE_PEAK={SURGE_PEAK.isoformat()}")

# -------------------- 1. Salesforce Accounts (~200) --------------------
N_ACCOUNTS = 200

_BRAND_PREFIX = ["Aurora", "Lumen", "Vertex", "Cobalt", "Marble", "Velvet", "Iron", "Sable", "Crest", "North",
                  "Bright", "Crimson", "Pine", "Granite", "Lark", "Ember", "Quartz", "Solstice", "Amber", "Onyx"]
_BRAND_SUFFIX = ["Studio", "Co", "Group", "Labs", "Atelier", "House", "Brands", "Collective", "Works", "Society"]
_PLAT_LIST_BRAND_PFX = F.array(*[F.lit(x) for x in _BRAND_PREFIX])
_PLAT_LIST_BRAND_SFX = F.array(*[F.lit(x) for x in _BRAND_SUFFIX])

def brand_name_expr(id_col):
    return F.concat_ws(" ",
        F.element_at(_PLAT_LIST_BRAND_PFX, ((id_col % len(_BRAND_PREFIX)) + 1).cast("int")),
        F.element_at(_PLAT_LIST_BRAND_SFX, ((F.abs(F.hash(id_col)) % len(_BRAND_SUFFIX)) + 1).cast("int")),
    )

industries = ["fashion", "beauty", "fitness", "food", "tech", "lifestyle", "luxury"]
countries = ["US", "FR", "UK", "DE", "JP", "BR"]
tiers = ["enterprise", "growth", "starter"]

acc = spark.range(0, N_ACCOUNTS, numPartitions=4).select(
    F.col("id"),
    F.concat(F.lit("ACC-"), F.lpad(F.col("id").cast("string"), 5, "0")).alias("account_id"),
    brand_name_expr(F.col("id")).alias("brand_name"),
    F.element_at(F.array(*[F.lit(x) for x in industries]),
                 (F.abs(F.hash("id")) % len(industries) + 1).cast("int")).alias("industry"),
    F.element_at(F.array(*[F.lit(x) for x in countries]),
                 (F.abs(F.hash(F.concat(F.col("id").cast("string"), F.lit("c")))) % len(countries) + 1).cast("int")).alias("country"),
    (F.lit(20000.0) + (F.abs(F.hash(F.concat(F.col("id").cast("string"), F.lit("a")))) % 480000).cast("double")).alias("arr_usd"),
)

# Apply tier (skewed) + renewal_status (skewed) + renewal_date
acc = acc.withColumn(
    "tier",
    F.when(F.rand(1) < 0.10, F.lit("enterprise"))
     .when(F.rand(2) < 0.45, F.lit("growth"))
     .otherwise(F.lit("starter"))
).withColumn(
    "renewal_status",
    F.when(F.rand(3) < 0.60, F.lit("renewed"))
     .when(F.rand(4) < 0.85, F.lit("up_for_renewal"))
     .when(F.rand(5) < 0.95, F.lit("upsell_candidate"))
     .otherwise(F.lit("churned"))
).withColumn(
    "renewal_arr_usd",
    F.when(F.col("tier") == "enterprise", F.col("arr_usd") * 1.0)
     .when(F.col("tier") == "growth", F.col("arr_usd") * 0.6)
     .otherwise(F.col("arr_usd") * 0.3)
).withColumn(
    "renewal_date",
    F.expr(f"date_add(current_date(), cast(rand() * 90 + 7 as int))")
).withColumn(
    "account_exec_email",
    F.concat(F.lit("ae"), (F.col("id") % 30).cast("string"), F.lit("@pulsar.com"))
).withColumn("created_at", F.lit(STORY_START)).withColumn("updated_at", F.lit(NOW)) \
 .drop("id")

# Override the 5 headline brands deterministically
headline = spark.createDataFrame([
    ("ACC-00001", "Coach", "fashion", "US", 400000.0, "enterprise", "up_for_renewal", 400000.0),
    ("ACC-00002", "L'Oréal", "beauty", "FR", 600000.0, "enterprise", "up_for_renewal", 320000.0),
    ("ACC-00003", "Adidas", "fitness", "DE", 500000.0, "enterprise", "up_for_renewal", 280000.0),
    ("ACC-00004", "Nike", "fitness", "US", 200000.0, "growth", "upsell_candidate", 120000.0),
    ("ACC-00005", "Sephora", "beauty", "US", 130000.0, "growth", "upsell_candidate", 80000.0),
], ["account_id", "brand_name", "industry", "country", "arr_usd", "tier", "renewal_status", "renewal_arr_usd"])

# Drop the rows in acc that collide with the headline IDs, keep the rest, union headline
acc_other = acc.filter(~F.col("account_id").isin([f"ACC-0000{i}" for i in range(1, 6)]))
acc_final = headline.withColumn("renewal_date", F.expr("date_add(current_date(), cast(rand() * 21 + 7 as int))")) \
                    .withColumn("account_exec_email", F.lit("maya.patel@pulsar.com")) \
                    .withColumn("created_at", F.lit(STORY_START)) \
                    .withColumn("updated_at", F.lit(NOW)) \
                    .unionByName(acc_other.select(headline.columns + ["renewal_date", "account_exec_email", "created_at", "updated_at"]))

acc_final.write.mode("overwrite").parquet(f"{RAW}/salesforce_accounts")
print(f"salesforce_accounts: {acc_final.count()} rows")

# Save to a Delta table for FK reuse downstream
acc_final.write.mode("overwrite").saveAsTable(f"{CATALOG}.{SCHEMA}._tmp_accounts")

# -------------------- 2. HubSpot Contacts (~800) --------------------
roles = ["account_exec", "marketing_lead", "billing"]
contacts = spark.range(0, 800, numPartitions=4).select(
    F.concat(F.lit("HUB-"), F.lpad(F.col("id").cast("string"), 6, "0")).alias("contact_id"),
    F.concat(F.lit("ACC-"), F.lpad(((F.col("id") % N_ACCOUNTS).cast("string")), 5, "0")).alias("account_id"),
    F.col("id"),
)

_FIRST = ["Alex", "Jordan", "Taylor", "Morgan", "Riley", "Casey", "Avery", "Skylar", "Quinn", "Reese",
          "Sam", "Drew", "Jamie", "Pat", "Robin", "Hayden", "Cameron", "Logan", "Emerson", "Rowan"]
_LAST = ["Smith", "Johnson", "Lee", "Brown", "Garcia", "Miller", "Davis", "Wilson", "Moore", "Taylor",
         "Anderson", "Thomas", "Jackson", "White", "Harris", "Martin", "Thompson", "Clark", "Lewis", "Walker"]
_FA = F.array(*[F.lit(x) for x in _FIRST])
_LA = F.array(*[F.lit(x) for x in _LAST])

contacts = contacts.withColumn("first_name", F.element_at(_FA, ((F.col("id") % len(_FIRST)) + 1).cast("int"))) \
    .withColumn("last_name", F.element_at(_LA, ((F.abs(F.hash(F.col("id"))) % len(_LAST)) + 1).cast("int"))) \
    .withColumn("email", F.concat(F.lower(F.col("first_name")), F.lit("."), F.lower(F.col("last_name")), F.lit("@example.com"))) \
    .withColumn("role", F.element_at(F.array(*[F.lit(r) for r in roles]), (F.abs(F.hash("id")) % 3 + 1).cast("int"))) \
    .withColumn("created_at", F.lit(STORY_START)).withColumn("updated_at", F.lit(NOW)) \
    .drop("id")

contacts.write.mode("overwrite").parquet(f"{RAW}/hubspot_contacts")
print(f"hubspot_contacts: {contacts.count()} rows")

# -------------------- 3. Creators master (used to derive CDC events) --------------------
N_CREATORS = 5000
creators_seed = spark.range(0, N_CREATORS, numPartitions=8).select(
    F.concat(F.lit("CR-"), F.lpad(F.col("id").cast("string"), 5, "0")).alias("creator_id"),
    F.col("id"),
)

creator_tiers = ["nano", "micro", "mid", "macro"]
platforms = ["tiktok", "instagram", "youtube"]
statuses = ["active", "paused", "under_review", "offboarded"]

creators_master = creators_seed.withColumn("handle",
        F.concat(F.lit("@"),
                 F.element_at(_FA, ((F.col("id") % len(_FIRST)) + 1).cast("int")),
                 F.lit("."),
                 F.element_at(_LA, ((F.abs(F.hash(F.col("id"))) % len(_LAST)) + 1).cast("int")),
                 (F.col("id") % 1000).cast("string"))
    ) \
    .withColumn("display_name",
        F.concat_ws(" ",
                    F.element_at(_FA, ((F.col("id") % len(_FIRST)) + 1).cast("int")),
                    F.element_at(_LA, ((F.abs(F.hash(F.col("id"))) % len(_LAST)) + 1).cast("int")))
    ) \
    .withColumn("tier",
        F.when(F.rand(7) < 0.50, F.lit("nano"))
         .when(F.rand(8) < 0.80, F.lit("micro"))
         .when(F.rand(9) < 0.95, F.lit("mid"))
         .otherwise(F.lit("macro"))) \
    .withColumn("platform",
        F.when(F.rand(10) < 0.60, F.lit("tiktok"))
         .when(F.rand(11) < 0.90, F.lit("instagram"))
         .otherwise(F.lit("youtube"))) \
    .withColumn("country", F.element_at(F.array(*[F.lit(c) for c in countries]), (F.abs(F.hash(F.concat(F.col("id").cast("string"), F.lit("c2")))) % len(countries) + 1).cast("int"))) \
    .withColumn("follower_count",
        F.when(F.col("tier") == "macro", (F.rand(12) * 4_000_000 + 1_000_000).cast("bigint"))
         .when(F.col("tier") == "mid", (F.rand(13) * 800_000 + 200_000).cast("bigint"))
         .when(F.col("tier") == "micro", (F.rand(14) * 90_000 + 10_000).cast("bigint"))
         .otherwise((F.rand(15) * 9_000 + 1_000).cast("bigint"))) \
    .withColumn("status",
        F.when(F.rand(16) < 0.75, F.lit("active"))
         .when(F.rand(17) < 0.90, F.lit("paused"))
         .when(F.rand(18) < 0.97, F.lit("under_review"))
         .otherwise(F.lit("offboarded"))) \
    .withColumn("agent_email", F.concat(F.lit("agent"), (F.col("id") % 50).cast("string"), F.lit("@pulsar.com"))) \
    .withColumn("joined_at", F.lit(STORY_START)) \
    .withColumn("updated_at", F.lit(NOW)) \
    .drop("id")

# Override headline creator CR-00042
cr42 = spark.createDataFrame([(
    "CR-00042", "@sofia.styles", "Sofia Martinelli", "macro", "tiktok", "IT",
    2_400_000, "active", "maya.patel@pulsar.com", STORY_START, NOW
)], creators_master.columns)
creators_master = creators_master.filter(F.col("creator_id") != "CR-00042").unionByName(cr42)

creators_master.write.mode("overwrite").saveAsTable(f"{CATALOG}.{SCHEMA}._tmp_creators")
print(f"_tmp_creators: {creators_master.count()} rows")

# -------------------- 4. Campaigns master (~2000) --------------------
N_CAMPAIGNS = 2000
camp_statuses = ["active", "paused", "ended"]

campaigns_master = spark.range(0, N_CAMPAIGNS, numPartitions=8).select(
    F.concat(F.lit("CMP-"), F.lpad(F.col("id").cast("string"), 5, "0")).alias("campaign_id"),
    F.concat(F.lit("ACC-"), F.lpad(((F.abs(F.hash("id")) % N_ACCOUNTS).cast("string")), 5, "0")).alias("account_id"),
    F.col("id"),
)

_COLOR = ["Crimson", "Azure", "Coral", "Olive", "Slate", "Gold", "Ivory", "Mint", "Plum", "Rose"]
_NOUN = ["Drop", "Edit", "Series", "Capsule", "Wave", "Story", "Bloom", "Rush", "Forge", "Echo"]
_VERB = ["Launch", "Reveal", "Spark", "Lift", "Push", "Rise", "Glow", "Flash", "Shine", "Burst"]
_CA = F.array(*[F.lit(x) for x in _COLOR])
_NA = F.array(*[F.lit(x) for x in _NOUN])
_VA = F.array(*[F.lit(x) for x in _VERB])

# Even spread of start_dates across 18 months, 30-90 day campaigns
campaigns_master = campaigns_master.withColumn("name",
        F.concat_ws(" ",
            F.element_at(_CA, ((F.col("id") % len(_COLOR)) + 1).cast("int")),
            F.element_at(_NA, ((F.abs(F.hash(F.col("id"))) % len(_NOUN)) + 1).cast("int")),
            F.element_at(_VA, ((F.abs(F.hash(F.concat(F.col("id").cast("string"), F.lit("v")))) % len(_VERB)) + 1).cast("int"))
        )) \
    .withColumn("_start_offset", (F.col("id").cast("double") / N_CAMPAIGNS * 540).cast("int")) \
    .withColumn("start_date", F.expr("date_sub(current_date(), 540 - _start_offset)")) \
    .withColumn("_dur", (F.rand(20) * 60 + 30).cast("int")) \
    .withColumn("end_date", F.expr("date_add(start_date, _dur)")) \
    .withColumn("budget_usd", (F.rand(21) * 495000 + 5000).cast("double")) \
    .withColumn("status",
        F.when(F.col("end_date") < F.current_date(), F.lit("ended"))
         .when(F.rand(22) < 0.10, F.lit("paused"))
         .otherwise(F.lit("active"))) \
    .withColumn("created_at", F.col("start_date").cast("timestamp")) \
    .withColumn("updated_at", F.lit(NOW)) \
    .drop("id", "_start_offset", "_dur")

# Headline campaign CMP-01337 → Coach (ACC-00001), active, current
cmp1337 = spark.createDataFrame([(
    "CMP-01337", "ACC-00001", "Coach Spring Capsule",
    (NOW - timedelta(days=70)).date(),
    (NOW + timedelta(days=15)).date(),
    250000.0, "active",
    NOW - timedelta(days=70), NOW
)], ["campaign_id", "account_id", "name", "start_date", "end_date", "budget_usd", "status", "created_at", "updated_at"])
campaigns_master = campaigns_master.filter(F.col("campaign_id") != "CMP-01337").unionByName(cmp1337)
campaigns_master.write.mode("overwrite").saveAsTable(f"{CATALOG}.{SCHEMA}._tmp_campaigns")
print(f"_tmp_campaigns: {campaigns_master.count()} rows")

# -------------------- 5. Google Ads spend (~50K) --------------------
# One row per (campaign, day-of-active-period) — sample daily over each campaign window, capped to ~50K total
camps = spark.table(f"{CATALOG}.{SCHEMA}._tmp_campaigns").select(
    "campaign_id", "start_date", "end_date", "status", "budget_usd"
)
spend = camps.withColumn("days", F.datediff("end_date", "start_date")) \
    .withColumn("date_seq", F.expr("sequence(start_date, end_date, interval 1 day)")) \
    .withColumn("date", F.explode("date_seq")) \
    .withColumn("clicks", (F.rand() * 5000 + 100).cast("int")) \
    .withColumn("impressions", (F.col("clicks") * (F.rand() * 50 + 20)).cast("bigint")) \
    .withColumn("daily_budget", F.col("budget_usd") / F.greatest(F.col("days"), F.lit(1))) \
    .withColumn("spend_usd",
        F.when(F.col("status") == "ended", F.col("daily_budget") * (F.rand() * 0.6 + 0.2))
         .when(F.col("status") == "paused", F.col("daily_budget") * (F.rand() * 0.2))
         .otherwise(F.col("daily_budget") * (F.rand() * 0.6 + 0.7))) \
    .withColumn("spend_id", F.concat(F.lit("SP-"), F.col("campaign_id"), F.lit("-"), F.date_format("date", "yyyyMMdd"))) \
    .select("spend_id", "campaign_id", "date", "clicks", "impressions", "spend_usd")
# Cap to ~50K via random sampling
spend = spend.sample(False, fraction=0.5, seed=99)
spend.write.mode("overwrite").parquet(f"{RAW}/google_ads_spend")
print(f"google_ads_spend: {spend.count()} rows")

# -------------------- 6. TikTok metrics (~1.2M) --------------------
# 5000 creators × ~240 days sampled = 1.2M
N_TIKTOK = 1_200_000
tiktok = spark.range(0, N_TIKTOK, numPartitions=32).select(
    F.concat(F.lit("TKM-"), F.lpad(F.col("id").cast("string"), 8, "0")).alias("metric_id"),
    F.concat(F.lit("CR-"), F.lpad(((F.abs(F.hash(F.concat(F.col("id").cast("string"), F.lit("c")))) % N_CREATORS).cast("string")), 5, "0")).alias("creator_id"),
    F.expr("date_sub(current_date(), cast(rand() * 540 as int))").alias("date"),
    (F.rand(30) * 200000 + 1000).cast("bigint").alias("impressions"),
    (F.rand(31) * 20000 + 100).cast("bigint").alias("engagements"),
    (F.rand(32) * 50000 + 500).cast("bigint").alias("video_views"),
    (F.rand(33) * 1000 + 5).cast("bigint").alias("comments"),
)
tiktok.write.mode("overwrite").parquet(f"{RAW}/tiktok_metrics")
print(f"tiktok_metrics: {tiktok.count()} rows")

# -------------------- 7. Stripe revenue (~100K) --------------------
# Brand subscription invoices (monthly, $5K-$30K per brand × 18 months × 200 = ~3600)
# + creator-attributed events (~96K)
brand_invoices = spark.table(f"{CATALOG}.{SCHEMA}._tmp_accounts").select("account_id").crossJoin(
    spark.range(0, 18).withColumnRenamed("id", "month_offset")
).select(
    F.concat(F.lit("TXN-"), F.lpad(F.monotonically_increasing_id().cast("string"), 8, "0")).alias("transaction_id"),
    F.lit("brand_invoice").alias("kind"),
    F.col("account_id"),
    F.lit(None).cast("string").alias("creator_id"),
    F.lit(None).cast("string").alias("campaign_id"),
    F.expr("date_sub(current_date(), cast(30 * month_offset as int))").alias("transaction_date"),
    (F.rand(40) * 25000 + 5000).cast("double").alias("amount_usd"),
    F.lit("USD").alias("currency"),
    F.lit("paid").alias("status"),
)

creator_attrib = spark.range(0, 96_500, numPartitions=16).select(
    F.concat(F.lit("TXNA-"), F.lpad(F.col("id").cast("string"), 8, "0")).alias("transaction_id"),
    F.lit("creator_attribution").alias("kind"),
    F.lit(None).cast("string").alias("account_id"),
    F.concat(F.lit("CR-"), F.lpad(((F.abs(F.hash(F.concat(F.col("id").cast("string"), F.lit("a")))) % N_CREATORS).cast("string")), 5, "0")).alias("creator_id"),
    F.concat(F.lit("CMP-"), F.lpad(((F.abs(F.hash(F.concat(F.col("id").cast("string"), F.lit("b")))) % N_CAMPAIGNS).cast("string")), 5, "0")).alias("campaign_id"),
    F.expr("date_sub(current_date(), cast(rand() * 540 as int))").alias("transaction_date"),
    (F.rand(50) * 1500 + 50).cast("double").alias("amount_usd"),
    F.lit("USD").alias("currency"),
    F.when(F.rand(51) < 0.92, F.lit("paid")).when(F.rand(52) < 0.97, F.lit("pending")).otherwise(F.lit("refunded")).alias("status"),
)

# Headline surge: CR-00042 attributed to Coach campaigns — generate a surge curve
import datetime as _dt
def surge_rows():
    """Return (txn_id, date, amount) tuples that produce the surge in the spec."""
    # week → target weekly attributed revenue
    weekly = [
        (12, 8000), (11, 8000), (10, 8000), (9, 8000), (8, 8000), (7, 8000),
        (6, 8500), (5, 9000), (4, 12000),
        (3, 48000), (2, 32000), (1, 22000), (0, 18000),
    ]
    rows = []
    txn_idx = 10_000_000
    for weeks_ago, total in weekly:
        # spread across 7 days, ~10 events per week → ~70 events average per week, more in surge
        n_events = max(8, total // 800)
        per = total / n_events
        for i in range(n_events):
            txn_idx += 1
            d = NOW - timedelta(weeks=weeks_ago, days=i % 7, hours=(i*3) % 24)
            rows.append((
                f"TXNS-{txn_idx:08d}", "creator_attribution", None, "CR-00042", "CMP-01337",
                d, float(per), "USD", "paid"
            ))
    return rows

from pyspark.sql.types import StructType, StructField, StringType as ST, DoubleType, DateType
surge_schema = StructType([
    StructField("transaction_id", ST(), False),
    StructField("kind", ST(), False),
    StructField("account_id", ST(), True),
    StructField("creator_id", ST(), True),
    StructField("campaign_id", ST(), True),
    StructField("transaction_date", DateType(), False),
    StructField("amount_usd", DoubleType(), False),
    StructField("currency", ST(), False),
    StructField("status", ST(), False),
])
surge_rows_dates = [(r[0], r[1], r[2], r[3], r[4], r[5].date(), r[6], r[7], r[8]) for r in surge_rows()]
surge_df = spark.createDataFrame(surge_rows_dates, surge_schema)
stripe = brand_invoices.unionByName(creator_attrib).unionByName(surge_df)
stripe.write.mode("overwrite").parquet(f"{RAW}/stripe_revenue")
print(f"stripe_revenue: {stripe.count()} rows")

# -------------------- 8. S3 contracts (~3K) --------------------
contracts = spark.range(0, 3000, numPartitions=4).select(
    F.concat(F.lit("CTR-"), F.lpad(F.col("id").cast("string"), 5, "0")).alias("contract_id"),
    F.concat(F.lit("ACC-"), F.lpad(((F.abs(F.hash("id")) % N_ACCOUNTS).cast("string")), 5, "0")).alias("account_id"),
    F.when(F.rand(60) < 0.4, F.concat(F.lit("CR-"), F.lpad(((F.abs(F.hash(F.concat(F.col("id").cast("string"), F.lit("k")))) % N_CREATORS).cast("string")), 5, "0"))).otherwise(F.lit(None)).alias("creator_id"),
    F.when(F.col("creator_id").isNotNull(), F.lit("creator_engagement")).otherwise(F.lit("brand_master")).alias("contract_type"),
    F.expr("date_sub(current_date(), cast(rand() * 540 as int))").alias("term_start"),
    F.col("id"),
)
contracts = contracts.withColumn("term_end", F.expr("date_add(term_start, 180 + cast(rand() * 365 as int))")) \
    .withColumn("contract_value_usd", (F.rand(61) * 95000 + 5000).cast("double")) \
    .withColumn("signed_at", F.col("term_start").cast("timestamp")) \
    .withColumn("status", F.when(F.col("term_end") < F.current_date(), F.lit("expired"))
                .when(F.rand(62) < 0.05, F.lit("terminated")).otherwise(F.lit("active"))) \
    .drop("id")
contracts.write.mode("overwrite").parquet(f"{RAW}/s3_contracts")
print(f"s3_contracts: {contracts.count()} rows")

# -------------------- 9. CDC events: creators (historical + demo, single write) --------------------
# Build everything as Spark DataFrames with identical schemas, union, then ONE overwrite.
# This avoids parquet schema fragmentation across files (Auto Loader cannot merge incompatible parquet schemas).
import time
from pyspark.sql.window import Window

late_ts = NOW - timedelta(hours=2)

# Historical creator INSERTs (payload built from _tmp_creators)
hist_creators_base = spark.table(f"{CATALOG}.{SCHEMA}._tmp_creators") \
    .withColumn("op", F.lit("INSERT")) \
    .withColumn("seq", F.row_number().over(Window.orderBy("creator_id")).cast("long")) \
    .withColumn("event_id", F.concat(F.lit("EV-CR-"), F.lpad(F.col("seq").cast("string"), 8, "0"))) \
    .withColumn("timestamp", F.lit(STORY_START).cast("timestamp")) \
    .withColumn("payload", F.struct(
        F.col("creator_id").cast("string").alias("creator_id"),
        F.col("handle").cast("string").alias("handle"),
        F.col("display_name").cast("string").alias("display_name"),
        F.col("tier").cast("string").alias("tier"),
        F.col("platform").cast("string").alias("platform"),
        F.col("country").cast("string").alias("country"),
        F.col("follower_count").cast("long").alias("follower_count"),
        F.col("status").cast("string").alias("status"),
        F.col("agent_email").cast("string").alias("agent_email"),
        F.col("joined_at").cast("timestamp").alias("joined_at"),
        F.col("updated_at").cast("timestamp").alias("updated_at"),
    )) \
    .select("event_id", "creator_id", "op", "seq", "timestamp", "payload")

N_HIST = hist_creators_base.count()
late_seq_start = N_HIST + 1

# Late events — express in pure SQL via a small inline DataFrame, then build payload with named_struct
late_creator_specs = [
    # (creator_id, op, status, tier, handle, display_name, country, follower_count)
    ("CR-00042", "UPDATE", "paused",        "macro", "@sofia.styles", "Sofia Martinelli", "IT", 2_400_000),
    ("CR-00198", "UPDATE", "active",        "mid",   "@user.cr00198", "Updated User",     "US", 200_000),
    ("CR-00715", "UPDATE", "offboarded",    "micro", "@user.cr00715", "Updated User",     "US", 50_000),
    ("CR-00301", "UPDATE", "under_review",  "micro", "@user.cr00301", "Updated User",     "US", 50_000),
    ("CR-00450", "UPDATE", "active",        "micro", "@user.cr00450", "Updated User",     "US", 50_000),
    ("CR-00811", "UPDATE", "active",        "micro", "@user.cr00811", "Updated User",     "US", 50_000),
]
late_creator_rows = []
for i, (cid, op, st, tier, handle, dn, ctry, fc) in enumerate(late_creator_specs):
    seq = late_seq_start + i
    late_creator_rows.append((
        f"EV-CR-{seq:08d}", cid, op, seq, cid, handle, dn, tier, "tiktok", ctry, int(fc), st,
        "maya.patel@pulsar.com",
    ))

late_creator_input = spark.createDataFrame(
    late_creator_rows,
    "event_id string, creator_id string, op string, seq long, p_creator_id string, p_handle string, p_display_name string, p_tier string, p_platform string, p_country string, p_follower_count long, p_status string, p_agent_email string"
)

late_creators = late_creator_input \
    .withColumn("timestamp", F.lit(late_ts).cast("timestamp")) \
    .withColumn("payload", F.struct(
        F.col("p_creator_id").alias("creator_id"),
        F.col("p_handle").alias("handle"),
        F.col("p_display_name").alias("display_name"),
        F.col("p_tier").alias("tier"),
        F.col("p_platform").alias("platform"),
        F.col("p_country").alias("country"),
        F.col("p_follower_count").alias("follower_count"),
        F.col("p_status").alias("status"),
        F.col("p_agent_email").alias("agent_email"),
        F.lit(STORY_START).cast("timestamp").alias("joined_at"),
        F.lit(late_ts).cast("timestamp").alias("updated_at"),
    )) \
    .select("event_id", "creator_id", "op", "seq", "timestamp", "payload")

# Single unified write — eliminates parquet schema fragmentation
all_creators = hist_creators_base.unionByName(late_creators)
all_creators.write.mode("overwrite").parquet(f"{CDC}/creators")
print(f"cdc_events/creators (unified): {all_creators.count()} rows")

# -------------------- 10. CDC events: campaigns (historical + demo, single write) --------------------
hist_camps_base = spark.table(f"{CATALOG}.{SCHEMA}._tmp_campaigns") \
    .withColumn("op", F.lit("INSERT")) \
    .withColumn("seq", F.row_number().over(Window.orderBy("campaign_id")).cast("long")) \
    .withColumn("event_id", F.concat(F.lit("EV-CMP-"), F.lpad(F.col("seq").cast("string"), 8, "0"))) \
    .withColumn("timestamp", F.col("created_at").cast("timestamp")) \
    .withColumn("payload", F.struct(
        F.col("campaign_id").cast("string").alias("campaign_id"),
        F.col("account_id").cast("string").alias("account_id"),
        F.col("name").cast("string").alias("name"),
        F.col("start_date").cast("date").alias("start_date"),
        F.col("end_date").cast("date").alias("end_date"),
        F.col("budget_usd").cast("double").alias("budget_usd"),
        F.col("status").cast("string").alias("status"),
        F.col("created_at").cast("timestamp").alias("created_at"),
        F.col("updated_at").cast("timestamp").alias("updated_at"),
    )) \
    .select("event_id", "campaign_id", "op", "seq", "timestamp", "payload")

N_HIST_CMP = hist_camps_base.count()
# Late campaign UPDATE for CMP-01337
late_camp_input = spark.createDataFrame(
    [(f"EV-CMP-{N_HIST_CMP+1:08d}", "CMP-01337", "UPDATE", int(N_HIST_CMP + 1))],
    "event_id string, campaign_id string, op string, seq long"
)
late_camps = late_camp_input \
    .withColumn("timestamp", F.lit(late_ts).cast("timestamp")) \
    .withColumn("payload", F.struct(
        F.lit("CMP-01337").cast("string").alias("campaign_id"),
        F.lit("ACC-00001").cast("string").alias("account_id"),
        F.lit("Coach Spring Capsule").cast("string").alias("name"),
        F.lit((NOW - timedelta(days=70)).date()).cast("date").alias("start_date"),
        F.lit((NOW + timedelta(days=20)).date()).cast("date").alias("end_date"),
        F.lit(250000.0).cast("double").alias("budget_usd"),
        F.lit("active").cast("string").alias("status"),
        F.lit(NOW - timedelta(days=70)).cast("timestamp").alias("created_at"),
        F.lit(late_ts).cast("timestamp").alias("updated_at"),
    )) \
    .select("event_id", "campaign_id", "op", "seq", "timestamp", "payload")

all_camps = hist_camps_base.unionByName(late_camps)
all_camps.write.mode("overwrite").parquet(f"{CDC}/campaigns")
print(f"cdc_events/campaigns (unified): {all_camps.count()} rows")

# -------------------- Cleanup tmp tables --------------------
spark.sql(f"DROP TABLE IF EXISTS {CATALOG}.{SCHEMA}._tmp_accounts")
spark.sql(f"DROP TABLE IF EXISTS {CATALOG}.{SCHEMA}._tmp_creators")
spark.sql(f"DROP TABLE IF EXISTS {CATALOG}.{SCHEMA}._tmp_campaigns")
print("Done.")
