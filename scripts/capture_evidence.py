"""Write evidence/RAW_EXECUTION_TRANSCRIPT.md from the live workspace and app.

Everything in the transcript is fetched at capture time (job run, run_log rows, UC tables, app
responses); nothing is typed in by hand.

    DATABRICKS_CONFIG_PROFILE=<profile> python scripts/capture_evidence.py --run-id <job run id> --app-url <url>
"""
import argparse
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import urllib.request

ap = argparse.ArgumentParser()
ap.add_argument("--run-id", required=True)
ap.add_argument("--app-url", required=True)
ap.add_argument("--warehouse", required=True)
ap.add_argument("--catalog", required=True)
ap.add_argument("--schema", default="renewal_radar")
ap.add_argument("--out", default="evidence/RAW_EXECUTION_TRANSCRIPT.md")
a = ap.parse_args()
FQ = f"{a.catalog}.{a.schema}"


def cli(*args):
    return subprocess.run(["databricks", *args], capture_output=True, text=True, check=True).stdout


def sql(statement):
    body = json.dumps({"warehouse_id": a.warehouse, "wait_timeout": "50s", "statement": statement})
    out = json.loads(cli("api", "post", "/api/2.0/sql/statements", "--json", body))
    assert out["status"]["state"] == "SUCCEEDED", out["status"]
    cols = [c["name"] for c in out["manifest"]["schema"]["columns"]]
    return cols, out.get("result", {}).get("data_array", [])


def table(cols, rows):
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    lines += ["| " + " | ".join("" if v is None else str(v).replace("|", "/") for v in r) + " |" for r in rows]
    return "\n".join(lines)


token = json.loads(cli("auth", "token", "-o", "json"))["access_token"]


def call(method, path, key="rr_demo_portfolio", body=None):
    req = urllib.request.Request(a.app_url + path, method=method, data=json.dumps(body).encode() if body else None,
                                 headers={"Authorization": f"Bearer {token}", "X-Api-Key": key, "Content-Type": "application/json"})
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=170) as r:
            status, text = r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        status, text = e.code, e.read().decode()
    return status, round((time.perf_counter() - t0) * 1000), text


out = [f"# Raw execution transcript\n\nCaptured {datetime.now(timezone.utc).isoformat(timespec='seconds')} by `scripts/capture_evidence.py`. "
       f"Every block below was fetched live at capture time.\n"]

# 1. Orchestration run
run = json.loads(cli("jobs", "get-run", a.run_id, "-o", "json"))
out.append(f"## 1. Orchestration run `{run['run_id']}`\n\nResult: **{run['state'].get('result_state')}** · {run['run_page_url']}\n")
rows = []
for t in run["tasks"]:
    secs = round(((t.get("end_time") or 0) - (t.get("start_time") or 0)) / 1000)
    rows.append((t["task_key"], t.get("attempt_number", 0), t["state"].get("result_state"), secs, ", ".join(d["task_key"] for d in t.get("depends_on", []))))
out.append(table(["task", "attempt", "result", "seconds", "depends_on"], rows) + "\n")

# 2. Task records written by each notebook
cols, recs = sql(f"SELECT task, recorded_at, payload FROM {FQ}.run_log ORDER BY recorded_at")
out.append("## 2. Task records (`run_log`, written by each task)\n")
for task, at, payload in recs:
    out.append(f"**{task}** at {at}\n```json\n{json.dumps(json.loads(payload), indent=1, sort_keys=True)}\n```\n")

# 3. Governed tables
out.append("## 3. Governed table profile\n")
parts = []
for t in ["bronze_social_events", "bronze_creator_sales", "bronze_ad_spend", "silver_campaign_day", "gold_campaign_performance",
          "platinum_creators", "platinum_campaigns", "platinum_campaign_roi", "brand_radar", "campaign_actions"]:
    parts.append(f"SELECT '{t}' AS table_name, COUNT(*) AS row_count FROM {FQ}.{t}")
out.append(table(*sql(" UNION ALL ".join(parts))) + "\n")

out.append("### Bottom-up value (`value_summary`)\n\n" + table(*sql(f"SELECT metric, ROUND(value, 0) AS value, unit, definition FROM {FQ}.value_summary ORDER BY metric")) + "\n")
out.append("### Renewal-risk bands (`brand_radar`)\n\n" + table(*sql(
    f"SELECT risk_band, COUNT(*) AS brands, ROUND(SUM(arr_usd)) AS arr_usd, ROUND(AVG(renewal_risk_score), 3) AS mean_score FROM {FQ}.brand_radar GROUP BY 1 ORDER BY 1")) + "\n")
out.append("### Regional seasonality (ROI by region and month, holiday peaks visible)\n\n" + table(*sql(
    f"SELECT region, date_format(month, 'yyyy-MM') AS month, ROUND(roi, 2) AS roi FROM {FQ}.gold_regional_seasonality WHERE region IN ('NA','APAC','LATAM') AND month >= add_months(current_date(), -12) ORDER BY region, month")) + "\n")

# 4. ai_gen output
cols, rows = sql(f"SELECT campaign_name, risk_band, ROUND(roi_90d,2), ROUND(benchmark_roi,2), ROUND(incremental_revenue_usd), recommendation FROM {FQ}.campaign_actions ORDER BY incremental_revenue_usd DESC LIMIT 5")
out.append("## 4. `ai_gen` actions (top 5 by opportunity; the prompt includes the brand's model risk score)\n\n" + table(["campaign", "risk_band", "roi_90d", "benchmark", "incremental_usd", "recommendation"], rows) + "\n")

# 5. Model registry and row-level security
cols, rows = sql(f"DESCRIBE EXTENDED {FQ}.brand_radar")
rf = [r for r in rows if r[0] and "filter" in str(r[0]).lower()]
out.append("## 5. Governance\n\nRow filter on `brand_radar` (from `DESCRIBE EXTENDED`):\n```\n" + "\n".join(" | ".join(map(str, r)) for r in rf) + "\n```\n")
mv = json.loads(cli("api", "get", f"/api/2.1/unity-catalog/models/{FQ}.renewal_risk/aliases/champion"))
out.append(f"Registered model `{FQ}.renewal_risk` alias `champion` -> version **{mv.get('version')}**\n")

# 6. App
out.append("## 6. Deployed app responses\n")
for label, method, path, key, body in [
    ("health (Lakebase round trip)", "GET", "/v1/health", "rr_demo_portfolio", None),
    ("brand key reads its own brand", "GET", "/v1/brands/ACC-0000/renewal-health", "rr_demo_brand_0000", None),
    ("brand key asks for ANOTHER brand -> 404", "GET", "/v1/brands/ACC-0001/renewal-health", "rr_demo_brand_0000", None),
    ("brand key asks for portfolio data -> 403", "GET", "/v1/portfolio/summary", "rr_demo_brand_0000", None),
    ("no key -> 401", "GET", "/v1/portfolio/summary", "", None),
    ("portfolio summary (book, renewals, spend, top at-risk)", "GET", "/v1/portfolio/summary", "rr_demo_portfolio", None),
    ("brand overview: the Saffron Beauty view", "GET", "/v1/brands/ACC-0118/overview", "rr_demo_brand_0118", None),
    ("brand key cannot open another brand's overview -> 404", "GET", "/v1/brands/ACC-0094/overview", "rr_demo_brand_0118", None),
    ("top persisted ai_gen actions", "GET", "/v1/portfolio/actions?limit=2", "rr_demo_portfolio", None),
    ("live foundation-model explanation", "POST", "/v1/campaigns/explain", "rr_demo_portfolio", {"campaign_id": "CMP-00080"}),
    ("Genie: API question -> script, no SQL", "POST", "/v1/genie/ask", "rr_demo_portfolio", {"question": "Which API endpoint shows renewal risk?"}),
    ("Genie asked from a BRAND view (scoped to that brand)", "POST", "/v1/genie/ask", "rr_demo_brand_0118", {"question": "What is our renewal risk?"}),
    ("that brand's question history (only its own view)", "GET", "/v1/genie/history?limit=5", "rr_demo_brand_0118", None),
    ("another brand's history is empty of those questions", "GET", "/v1/genie/history?limit=5", "rr_demo_brand_0094", None),
    ("operator history: all views, with asker and view", "GET", "/v1/genie/history?limit=6", "rr_demo_portfolio", None),
    ("Genie: analytical question -> inspectable SQL", "POST", "/v1/genie/ask", "rr_demo_portfolio", {"question": "Which region has the lowest ROI?"}),
]:
    status, ms, text = call(method, path, key, body)
    try:
        text = json.dumps(json.loads(text), indent=1)
    except Exception:
        pass
    out.append(f"**{label}**: `{method} {path}` -> HTTP {status} in {ms} ms\n```json\n{text[:2600]}\n```\n")

status, ms, text = call("GET", "/v1/telemetry/recent")
cols = ["ts", "method", "route", "status", "duration_ms", "key_label"]
out.append("### Request log (`radar_app.request_log` in Lakebase)\n\n" + table(cols, [[r[c] for c in cols] for r in json.loads(text)[:12]]) + "\n")

Path(a.out).parent.mkdir(exist_ok=True)
Path(a.out).write_text("\n".join(out))
print(f"wrote {a.out} ({len(out)} sections)")
