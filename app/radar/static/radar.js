const $ = (s) => document.querySelector(s);
const money = (n) => "$" + Math.round(Number(n)).toLocaleString();
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const keyEl = $("#key");
const TITLES = { outcome: "Overview", risk: "Renewal risk", actions: "AI actions", genie: "Ask Genie", pipeline: "Pipeline & telemetry" };

async function api(path, opts = {}) {
  const res = await fetch(path, { ...opts, headers: { "X-Api-Key": keyEl.value, "Content-Type": "application/json", ...(opts.headers || {}) } });
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch (_) {}
    throw new Error(`${res.status} ${detail}`);
  }
  return res.json();
}
const fail = (el, e) => { el.innerHTML = `<p class="err">${esc(e.message)}</p>`; };
const isPortfolio = () => keyEl.value.includes("portfolio");
const brandId = () => { const m = keyEl.value.match(/brand_(\d{4})/); return m ? "ACC-" + m[1] : null; };
const current = () => document.querySelector("#tabs .on").dataset.tab;

function roleHint() {
  $("#rolehint").textContent = isPortfolio() ? "Sees every brand and the portfolio views." : `Sees only ${brandId()}. Other brands return 404.`;
}

document.querySelectorAll("#tabs button").forEach((b) => b.addEventListener("click", () => {
  document.querySelectorAll("#tabs button, .pane").forEach((x) => x.classList.remove("on"));
  b.classList.add("on"); $("#" + b.dataset.tab).classList.add("on");
  $("#title").textContent = $("#crumb").textContent = TITLES[b.dataset.tab];
  load(b.dataset.tab);
}));
keyEl.addEventListener("change", () => { roleHint(); load(current()); });

const root = document.documentElement;
root.dataset.theme = localStorage.getItem("radar-theme") || "light";
$("#theme").addEventListener("click", () => {
  root.dataset.theme = root.dataset.theme === "dark" ? "light" : "dark";
  localStorage.setItem("radar-theme", root.dataset.theme);
});

async function load(tab) {
  if (tab === "outcome") return outcome();
  if (tab === "risk") return risk();
  if (tab === "actions") return actions();
  if (tab === "genie") return history();
  if (tab === "pipeline") return pipeline();
}

async function outcome() {
  const cards = $("#cards");
  $("#mix").innerHTML = $("#mixlegend").innerHTML = $("#region").innerHTML = "";
  if (!isPortfolio()) return brandOutcome(cards);
  try {
    const s = await api("/v1/portfolio/summary");
    const by = Object.fromEntries(s.risk_by_band.map((b) => [b.risk_band, b]));
    const high = by.high || { brands: 0, arr_usd: 0 };
    const total = s.risk_by_band.reduce((a, b) => a + Number(b.arr_usd), 0);
    const t = s.top_actions;
    cards.innerHTML = `
      <div class="card risk"><div class="l">ARR in brands scored high renewal risk</div><div class="v">${money(high.arr_usd)}</div><div class="d">${high.brands} brands · ${Math.round((high.arr_usd / total) * 100)}% of ${money(total)} portfolio ARR</div></div>
      <div class="card good"><div class="l">Revenue from moving 30% of spend off underperformers</div><div class="v">${money(t.incremental_revenue_usd)}</div><div class="d">Across the ${t.campaigns} largest gaps · ROI below 1.0 vs regional benchmark</div></div>
      <div class="card"><div class="l">90-day spend on those campaigns</div><div class="v">${money(t.spend_90d_usd)}</div><div class="d">Served from Lakebase, not a warehouse</div></div>`;
    const colors = { high: "var(--high)", medium: "var(--med)", low: "var(--low)" };
    $("#mix").innerHTML = ["high", "medium", "low"].filter((k) => by[k]).map((k) => `<span style="width:${(by[k].brands / s.risk_by_band.reduce((a, b) => a + b.brands, 0)) * 100}%;background:${colors[k]}"></span>`).join("");
    $("#mixlegend").innerHTML = ["high", "medium", "low"].filter((k) => by[k]).map((k) => `<span><i class="sw" style="background:${colors[k]}"></i><b>${by[k].brands}</b> ${k} · ${money(by[k].arr_usd)}</span>`).join("");
    const max = Math.max(...s.roi_by_region.map((r) => Number(r.roi)));
    $("#region").innerHTML = s.roi_by_region.map((r) => `<div class="row"><span>${esc(r.region)}</span><div class="bar" style="width:${(Number(r.roi) / max) * 100}%"></div><span class="n">${esc(r.roi)}x</span></div>`).join("");
    $("#valuenote").textContent = "Every figure is computed from governed rows; the sizing logic is gold_reallocation_opportunity in the pipeline.";
  } catch (e) { fail(cards, e); }
}

async function brandOutcome(cards) {
  try {
    const h = await api(`/v1/brands/${brandId()}/renewal-health`);
    cards.innerHTML = `
      <div class="card ${h.risk_band === "high" ? "risk" : "good"}"><div class="l">${esc(h.brand_name)} modelled churn probability</div><div class="v">${Math.round(h.renewal_risk_score * 100)}%</div><div class="d"><span class="pill ${esc(h.risk_band)}">${esc(h.risk_band)}</span> · ARR ${money(h.arr_usd)}</div></div>
      <div class="card"><div class="l">90-day ROI of active campaigns</div><div class="v">${Number(h.avg_roi_180d).toFixed(2)}x</div><div class="d">${h.active_campaigns} campaigns active in the last 90 days</div></div>
      <div class="card"><div class="l">Revenue trend, last 90 days</div><div class="v">${(h.revenue_trend_90d * 100).toFixed(0)}%</div><div class="d">Late invoices: ${(h.late_invoice_rate * 100).toFixed(0)}%</div></div>`;
    $("#valuenote").textContent = "A brand-scoped key sees only its own account. Any other account id returns 404.";
  } catch (e) { fail(cards, e); }
}

async function risk() {
  const body = $("#risktable tbody");
  try {
    const rows = isPortfolio() ? await api("/v1/portfolio/risk?limit=30") : [await api(`/v1/brands/${brandId()}/renewal-health`)];
    body.innerHTML = rows.map((r) => `<tr><td>${esc(r.brand_name)}<div class="sub">${esc(r.account_id)}</div></td><td>${esc(r.region)}</td><td>${esc(r.tier)}</td><td class="n">${money(r.arr_usd)}</td><td class="n">${esc((r.renewal_date || "").slice(0, 10))}</td><td class="n">${Math.round(r.renewal_risk_score * 100)}%</td><td><span class="pill ${esc(r.risk_band)}">${esc(r.risk_band)}</span></td></tr>`).join("");
  } catch (e) { body.innerHTML = `<tr><td colspan="7" class="err">${esc(e.message)}</td></tr>`; }
}

async function actions() {
  const list = $("#actionlist");
  list.innerHTML = '<div class="skeleton"></div>';
  try {
    const recs = await api(isPortfolio() ? "/v1/portfolio/actions?limit=15" : `/v1/brands/${brandId()}/recommendations`);
    list.innerHTML = recs.length ? recs.map((r) => `
      <div class="item"><div class="t"><span>${esc(r.campaign_name)}</span><span class="pill ${esc(r.risk_band)}">${esc(r.risk_band)} risk</span></div>
        <div class="m">90-day ROI ${Number(r.roi_90d).toFixed(2)}x vs benchmark ${Number(r.benchmark_roi).toFixed(2)}x · ${money(r.spend_90d_usd)} spend · +${money(r.incremental_revenue_usd)}/yr if 30% moves</div>
        <div>${esc(r.recommendation)}</div>
        <p><button data-c="${esc(r.campaign_id)}">Explain with live model</button> <span class="note" id="ex-${esc(r.campaign_id)}"></span></p></div>`).join("")
      : '<p class="note">No flagged campaigns for this brand.</p>';
    list.querySelectorAll("button").forEach((b) => b.addEventListener("click", async () => {
      const out = document.getElementById("ex-" + b.dataset.c); out.textContent = "calling model...";
      try {
        const r = await api("/v1/campaigns/explain", { method: "POST", body: JSON.stringify({ campaign_id: b.dataset.c }) });
        out.innerHTML = `${esc(r.explanation)} <em>(${esc(r.endpoint)}, ${r.latency_ms} ms, ${esc(r.usage.total_tokens || "?")} tokens)</em>`;
      } catch (e) { out.innerHTML = `<span class="err">${esc(e.message)}</span>`; }
    }));
  } catch (e) { fail(list, e); }
}

async function history() {
  const body = $("#history tbody");
  const operator = isPortfolio();
  $("#history").hidden = !operator;
  $("#histnote").hidden = operator;
  $("#histcount").textContent = "";
  if (!operator) return;
  try {
    const rows = await api("/v1/genie/history?limit=30");
    $("#histcount").textContent = `(${rows.length} most recent)`;
    body.innerHTML = rows.length ? rows.map((r) => `<tr><td>${esc(r.ts.slice(0, 19).replace("T", " "))}</td><td>${esc(r.asked_by || "—")}</td>
      <td>${esc(r.question)}${r.genie_url ? ` <a href="${esc(r.genie_url)}" target="_blank" rel="noopener">conversation</a>` : ""}</td>
      <td>${r.intent ? `<span class="tag">${esc(r.intent)}</span>` : ""}</td><td class="n">${esc(r.duration_ms)}</td>
      <td>${r.status === 200 ? '<span class="tag ok">answered</span>' : `<span class="tag bad" title="${esc(r.error)}">failed</span>`}</td></tr>`).join("")
      : '<tr><td colspan="6" class="note">No questions yet.</td></tr>';
  } catch (e) { body.innerHTML = `<tr><td colspan="6" class="err">${esc(e.message)}</td></tr>`; }
}

$("#askbtn").addEventListener("click", async () => {
  const out = $("#answer");
  out.innerHTML = '<div class="skeleton"></div>';
  try {
    const r = await api("/v1/genie/ask", { method: "POST", body: JSON.stringify({ question: $("#q").value }) });
    let html = `<p>${esc(r.answer)}</p>`;
    if (r.api_call) html += `<p><strong>${esc(r.api_call.method)} ${esc(r.api_call.path)}</strong>: ${esc(r.api_call.purpose)}</p><pre>${esc(r.api_call.script)}</pre>`;
    (r.queries || []).forEach((q) => { html += `<p class="note">${esc(q.description || "Generated SQL")}</p><pre>${esc(q.sql)}</pre>`; });
    html += `<p class="note">Genie conversation: <a href="${esc(r.genie_url)}" target="_blank" rel="noopener">${esc(r.conversation_id)}</a></p>`;
    out.innerHTML = html;
  } catch (e) { fail(out, e); }
  history();
});

async function pipeline() {
  const run = $("#run"), body = $("#reqs tbody");
  if (!isPortfolio()) {
    run.innerHTML = '<p class="note">Run timings and the request log are visible to portfolio operators only.</p>';
    body.innerHTML = "";
    return;
  }
  try {
    const r = await api("/v1/pipeline/last-run");
    run.innerHTML = `<p class="note">Run <a href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.run_id)}</a>: <span class="tag ${r.result === "SUCCESS" ? "ok" : "bad"}">${esc(r.result)}</span> ${r.total_seconds}s end to end</p>
      <table><thead><tr><th>Task</th><th>Result</th><th class="n">Seconds</th></tr></thead><tbody>${r.tasks.map((t) => `<tr><td>${esc(t.task)}</td><td>${esc(t.result)}</td><td class="n">${t.seconds}</td></tr>`).join("")}</tbody></table>`;
    const rows = await api("/v1/telemetry/recent");
    body.innerHTML = rows.map((x) => `<tr><td>${esc(x.ts.slice(11, 19))}</td><td>${esc(x.method)} ${esc(x.route)}</td><td class="n">${x.status}</td><td class="n">${esc(x.duration_ms)}</td><td>${esc(x.key_label || "")}</td></tr>`).join("");
  } catch (e) { fail(run, e); }
}

roleHint();
outcome();
