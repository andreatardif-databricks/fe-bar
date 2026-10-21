const $ = (s) => document.querySelector(s);
const money = (n) => "$" + Math.round(Number(n)).toLocaleString();
const keyEl = $("#key");
let cache = {};

async function api(path, opts = {}) {
  const res = await fetch(path, { ...opts, headers: { "X-Api-Key": keyEl.value, "Content-Type": "application/json", ...(opts.headers || {}) } });
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch (_) {}
    throw new Error(`${res.status} ${detail}`);
  }
  return res.json();
}
const fail = (el, e) => { el.innerHTML = `<p class="err">${e.message}</p>`; };
const isPortfolio = () => keyEl.value.includes("portfolio");
const brandId = () => (keyEl.value.match(/brand_(\d{4})/) || [])[1] ? "ACC-" + keyEl.value.match(/brand_(\d{4})/)[1] : null;

document.querySelectorAll("#tabs button").forEach((b) => b.addEventListener("click", () => {
  document.querySelectorAll("#tabs button, .pane").forEach((x) => x.classList.remove("on"));
  b.classList.add("on"); $("#" + b.dataset.tab).classList.add("on");
  load(b.dataset.tab);
}));
keyEl.addEventListener("change", () => { cache = {}; load(document.querySelector("#tabs .on").dataset.tab); });

async function load(tab) {
  if (tab === "outcome") return outcome();
  if (tab === "risk") return risk();
  if (tab === "actions") return actions();
  if (tab === "pipeline") return pipeline();
}

async function outcome() {
  const cards = $("#cards");
  if (!isPortfolio()) { cards.innerHTML = ""; $("#region").innerHTML = ""; return brandOutcome(cards); }
  try {
    const s = await api("/v1/portfolio/summary");
    const high = s.risk_by_band.find((b) => b.risk_band === "high") || { brands: 0, arr_usd: 0 };
    const t = s.top_actions;
    cards.innerHTML = `
      <div class="card"><div class="l">ARR in brands scored high renewal risk</div><div class="v">${money(high.arr_usd)}</div><div class="d">${high.brands} brands, scored by the UC-registered champion model</div></div>
      <div class="card"><div class="l">Revenue from moving 30% of spend off underperformers</div><div class="v">${money(t.incremental_revenue_usd)}</div><div class="d">Across the ${t.campaigns} largest gaps; ROI below 1.0 versus the regional benchmark</div></div>
      <div class="card"><div class="l">90-day spend on those campaigns</div><div class="v">${money(t.spend_90d_usd)}</div><div class="d">Served from Lakebase in milliseconds, not from a warehouse</div></div>`;
    const max = Math.max(...s.roi_by_region.map((r) => Number(r.roi)));
    $("#region").innerHTML = s.roi_by_region.map((r) => `<div class="row"><span>${r.region}</span><div class="bar" style="width:${(Number(r.roi) / max) * 100}%"></div><span class="n">${r.roi}x</span></div>`).join("");
    $("#valuenote").textContent = "Every figure on this page is computed from governed rows; the sizing logic is gold_reallocation_opportunity in the pipeline.";
  } catch (e) { fail(cards, e); }
}

async function brandOutcome(cards) {
  try {
    const h = await api(`/v1/brands/${brandId()}/renewal-health`);
    cards.innerHTML = `
      <div class="card"><div class="l">${h.brand_name} modelled churn probability</div><div class="v">${Math.round(h.renewal_risk_score * 100)}%</div><div class="d"><span class="pill ${h.risk_band}">${h.risk_band}</span> ARR ${money(h.arr_usd)}</div></div>
      <div class="card"><div class="l">90-day ROI of active campaigns</div><div class="v">${Number(h.avg_roi_180d).toFixed(2)}x</div><div class="d">${h.active_campaigns} campaigns active in the last 30 days</div></div>
      <div class="card"><div class="l">Revenue trend, last 90 days</div><div class="v">${(h.revenue_trend_90d * 100).toFixed(0)}%</div><div class="d">Late invoices: ${(h.late_invoice_rate * 100).toFixed(0)}%</div></div>`;
    $("#valuenote").textContent = "A brand-scoped key sees only its own account. Any other account id returns 404.";
  } catch (e) { fail(cards, e); }
}

async function risk() {
  const body = $("#risktable tbody");
  try {
    const rows = isPortfolio() ? await api("/v1/portfolio/risk?limit=30") : [await api(`/v1/brands/${brandId()}/renewal-health`)];
    $("#risktitle").textContent = isPortfolio() ? "Brands ranked by modelled churn probability" : "Your brand";
    body.innerHTML = rows.map((r) => `<tr><td>${r.brand_name}<div class="note">${r.account_id}</div></td><td>${r.region}</td><td>${r.tier}</td><td class="n">${money(r.arr_usd)}</td><td class="n">${(r.renewal_date || "").slice(0, 10)}</td><td class="n">${Math.round(r.renewal_risk_score * 100)}%</td><td><span class="pill ${r.risk_band}">${r.risk_band}</span></td></tr>`).join("");
  } catch (e) { body.innerHTML = `<tr><td colspan="7" class="err">${e.message}</td></tr>`; }
}

async function actions() {
  const list = $("#actionlist");
  list.innerHTML = '<div class="skeleton"></div>';
  try {
    const recs = await api(isPortfolio() ? "/v1/portfolio/actions?limit=15" : `/v1/brands/${brandId()}/recommendations`);
    list.innerHTML = recs.length ? recs.map((r) => `
      <div class="item"><div class="t"><span>${r.campaign_name}<span class="note"> ${r.region || ""}</span></span><span class="pill ${r.risk_band}">${r.risk_band} risk</span></div>
        <div class="m">90-day ROI ${Number(r.roi_90d).toFixed(2)}x vs benchmark ${Number(r.benchmark_roi).toFixed(2)}x · ${money(r.spend_90d_usd)} spend · +${money(r.incremental_revenue_usd)}/yr if 30% moves</div>
        <div>${r.recommendation}</div>
        <p><button data-c="${r.campaign_id}">Explain with live model</button> <span class="note" id="ex-${r.campaign_id}"></span></p></div>`).join("")
      : '<p class="note">No flagged campaigns for this brand.</p>';
    list.querySelectorAll("button").forEach((b) => b.addEventListener("click", async () => {
      const out = $("#ex-" + b.dataset.c); out.textContent = "calling model...";
      try { const r = await api("/v1/campaigns/explain", { method: "POST", body: JSON.stringify({ campaign_id: b.dataset.c }) });
        out.innerHTML = `${r.explanation} <em>(${r.endpoint}, ${r.latency_ms} ms, ${r.usage.total_tokens || "?"} tokens)</em>`; }
      catch (e) { out.innerHTML = `<span class="err">${e.message}</span>`; }
    }));
  } catch (e) { fail(list, e); }
}

$("#askbtn").addEventListener("click", async () => {
  const out = $("#answer");
  out.innerHTML = '<div class="skeleton"></div>';
  try {
    const r = await api("/v1/genie/ask", { method: "POST", body: JSON.stringify({ question: $("#q").value }) });
    let html = `<p>${r.answer || ""}</p>`;
    if (r.api_call) html += `<p><strong>${r.api_call.method} ${r.api_call.path}</strong>: ${r.api_call.purpose}</p><pre>${r.api_call.script}</pre>`;
    (r.queries || []).forEach((q) => { html += `<p class="note">${q.description || "Generated SQL"}</p><pre>${q.sql}</pre>`; });
    html += `<p class="note">Genie conversation: <a href="${r.genie_url}" target="_blank" rel="noopener">${r.conversation_id}</a></p>`;
    out.innerHTML = html;
  } catch (e) { fail(out, e); }
});

async function pipeline() {
  const run = $("#run"), body = $("#reqs tbody");
  try {
    const r = await api("/v1/pipeline/last-run");
    run.innerHTML = `<p class="note">Run <a href="${r.url}" target="_blank" rel="noopener">${r.run_id}</a>: ${r.result}, ${r.total_seconds}s end to end</p>
      <table><thead><tr><th>Task</th><th>Result</th><th class="n">Seconds</th></tr></thead><tbody>${r.tasks.map((t) => `<tr><td>${t.task}</td><td>${t.result}</td><td class="n">${t.seconds}</td></tr>`).join("")}</tbody></table>`;
    const rows = await api("/v1/telemetry/recent");
    body.innerHTML = rows.map((x) => `<tr><td>${x.ts.slice(11, 19)}</td><td>${x.method} ${x.route}</td><td class="n">${x.status}</td><td class="n">${x.duration_ms}</td><td>${x.key_label || ""}</td></tr>`).join("");
  } catch (e) { fail(run, e); }
}

outcome();
