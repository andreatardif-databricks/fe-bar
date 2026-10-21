const $ = (s) => document.querySelector(s);
const money = (n) => "$" + Math.round(Number(n)).toLocaleString();
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const keyEl = $("#key");
const TITLES = { outcome: "Overview", risk: "Renewal risk", actions: "AI actions", genie: "Ask Genie", pipeline: "Data & activity" };

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

const pct = (x, d = 0) => (Number(x) * 100).toFixed(d) + "%";
const card = (cls, label, value, detail) => `<div class="card ${cls}"><div class="l">${label}</div><div class="v">${value}</div><div class="d">${detail}</div></div>`;
const vs = (x, ref, label, higherIsBetter = true) => {
  const diff = Number(x) - Number(ref);
  const good = higherIsBetter ? diff >= 0 : diff <= 0;
  return `<span class="${good ? "up" : "down"}">${diff >= 0 ? "▲" : "▼"} ${Math.abs(diff).toFixed(2)}</span> vs ${label}`;
};

const churnVs = (mine, ref, region) => {
  const pts = Math.round((Number(mine) - Number(ref)) * 100);
  return `<span class="${pts <= 0 ? "up" : "down"}">${pts <= 0 ? "▼" : "▲"} ${Math.abs(pts)} pts</span> vs ${esc(region)} average`;
};

async function outcome() {
  const ov = $("#ov");
  ov.innerHTML = '<div class="cards"><div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div></div>';
  try { return isPortfolio() ? await portfolioOverview(ov) : await brandOverview(ov); } catch (e) { fail(ov, e); }
}

async function portfolioOverview(ov) {
  const s = await api("/v1/portfolio/summary");
  const by = Object.fromEntries(s.risk_by_band.map((b) => [b.risk_band, b]));
  const high = by.high || { brands: 0, arr_usd: 0 };
  const bk = s.book, sp = s.spend, t = s.top_actions;
  const total = s.risk_by_band.reduce((a, b) => a + Number(b.arr_usd), 0);
  const nBrands = s.risk_by_band.reduce((a, b) => a + b.brands, 0);
  const colors = { high: "var(--high)", medium: "var(--med)", low: "var(--low)" };
  const max = Math.max(...s.roi_by_region.map((r) => Number(r.roi)));
  ov.innerHTML = `
    <div class="cards">
      ${card("risk", "ARR in brands scored high renewal risk", money(high.arr_usd), `${high.brands} brands · ${Math.round((high.arr_usd / total) * 100)}% of ${money(total)} ARR`)}
      ${card("risk", "Probability-weighted ARR at risk", money(bk.expected_loss_usd), `${pct(bk.expected_loss_usd / bk.arr_usd)} of ARR · synthetic labels run high`)}
      ${card("", "Renewing within 90 days", `${bk.renewing_90d} brands`, `${money(bk.renewing_90d_arr)} ARR · <b>${bk.high_risk_renewing_90d}</b> high-risk (${money(bk.high_risk_renewing_90d_arr)})`)}
      ${card("good", "Revenue from moving 30% of spend off underperformers", money(t.incremental_revenue_usd), `Across the ${t.campaigns} largest gaps · ${money(t.spend_90d_usd)} 90-day spend`)}
    </div>
    <div class="cards">
      ${card("", "Portfolio ROI (lifetime)", Number(sp.roi).toFixed(2) + "x", `${money(sp.revenue_usd)} revenue on ${money(sp.spend_usd)} spend`)}
      ${card("", "Campaigns", sp.campaigns.toLocaleString(), `${sp.active} active · <b>${sp.below_breakeven}</b> below break-even (90-day ROI &lt; 1.0)`)}
      ${card("", "Average churn probability", pct(bk.avg_churn), `Across ${bk.brands} brands`)}
      ${card("", "Genie questions asked", s.genie_questions, "Recorded in Lakebase; see Ask Genie")}
    </div>
    <div class="grid2">
      <div class="panel"><h2>Renewal risk mix</h2>
        <div class="mix">${["high", "medium", "low"].filter((k) => by[k]).map((k) => `<span style="width:${(by[k].brands / nBrands) * 100}%;background:${colors[k]}"></span>`).join("")}</div>
        <div class="legend">${["high", "medium", "low"].filter((k) => by[k]).map((k) => `<span><i class="sw" style="background:${colors[k]}"></i><b>${by[k].brands}</b> ${k} · ${money(by[k].arr_usd)}</span>`).join("")}</div></div>
      <div class="panel"><h2>ROI by region</h2><div class="bars">${s.roi_by_region.map((r) => `<div class="row"><span>${esc(r.region)}</span><div class="bar" style="width:${(Number(r.roi) / max) * 100}%"></div><span class="n">${esc(r.roi)}x</span></div>`).join("")}</div></div>
    </div>
    <div class="grid2">
      <div class="panel flush"><h2 class="pad">Risk by region</h2><table><thead><tr><th>Region</th><th class="n">Brands</th><th class="n">ARR</th><th class="n">Avg churn</th><th class="n">High risk</th></tr></thead><tbody>
        ${s.by_region.map((r) => `<tr><td>${esc(r.region)}</td><td class="n">${r.brands}</td><td class="n">${money(r.arr_usd)}</td><td class="n">${esc(r.avg_churn_pct)}%</td><td class="n">${r.high_risk}</td></tr>`).join("")}</tbody></table></div>
      <div class="panel flush"><h2 class="pad">Top 5 brands by expected ARR loss</h2><table><thead><tr><th>Brand</th><th class="n">ARR</th><th class="n">Churn</th><th class="n">Renewal</th></tr></thead><tbody>
        ${s.top_at_risk.map((r) => `<tr><td>${esc(r.brand_name)}<div class="sub">${esc(r.region)} · ${esc(r.tier)}</div></td><td class="n">${money(r.arr_usd)}</td><td class="n">${pct(r.renewal_risk_score)}</td><td class="n">${esc(String(r.renewal_date).slice(0, 10))}</td></tr>`).join("")}</tbody></table></div>
    </div>
    <p class="note">Every figure is computed from governed rows; the sizing logic is gold_reallocation_opportunity in the pipeline.</p>`;
}

async function brandOverview(ov) {
  const o = await api(`/v1/brands/${brandId()}/overview`);
  const b = o.brand, c = o.campaigns, a = o.actions, rp = o.risk_peers, rk = o.roi_rank;
  const days = Number(b.days_to_renewal);
  const renewal = days < 0 ? `renewal date passed ${-days} days ago` : `renews in ${days} days (${String(b.renewal_date).slice(0, 10)})`;
  const hl = (x, label) => x && x.campaign_name ? `<div class="hl"><b>${label}</b> ${esc(x.campaign_name)}<div class="sub">${Number(x.roi).toFixed(2)}x ROI on ${money(x.spend_usd)} spend</div></div>` : "";
  ov.innerHTML = `
    <div class="cards">
      ${card(b.risk_band === "high" ? "risk" : b.risk_band === "low" ? "good" : "", `${esc(b.brand_name)} modelled churn probability`, pct(b.renewal_risk_score), `<span class="pill ${esc(b.risk_band)}">${esc(b.risk_band)}</span> · ${churnVs(b.renewal_risk_score, rp.region_churn, b.region)}`)}
      ${card("", "Annual recurring revenue", money(b.arr_usd), `${esc(b.tier)} tier · ${renewal}`)}
      ${card("", "Lifetime ROI", Number(c.roi).toFixed(2) + "x", `${vs(c.roi, o.region_roi, esc(b.region) + " average")} · rank <b>${rk.rank}</b> of ${rk.brands} brands`)}
      ${card("good", "Revenue if 30% of spend moves off weak campaigns", money(a.opportunity_usd), `${a.flagged} flagged campaigns · ${money(a.spend_90d_usd)} 90-day spend`)}
    </div>
    <div class="cards">
      ${card("", "Total ad spend", money(c.spend_usd), `${c.campaigns} campaigns run for this brand`)}
      ${card("", "Attributed revenue", money(c.revenue_usd), "Paid sales credited to creator campaigns")}
      ${card("", "Campaign portfolio", `${c.active} active`, `${c.ended} ended · <b>${c.below_breakeven}</b> below break-even right now`)}
      ${card("", "Revenue trend, last 90 days", pct(b.revenue_trend_90d), `Late invoices: ${pct(b.late_invoice_rate)}`)}
    </div>
    <div class="grid2">
      <div class="panel flush"><h2 class="pad">What drives your score</h2><table><thead><tr><th>Driver</th><th class="n">You</th><th class="n">${esc(b.region)} / portfolio</th></tr></thead><tbody>
        <tr><td>90-day ROI</td><td class="n">${Number(b.avg_roi_180d).toFixed(2)}x</td><td class="n">${Number(o.region_roi).toFixed(2)}x</td></tr>
        <tr><td>Campaigns active in last 90 days</td><td class="n">${b.active_campaigns}</td><td class="n">—</td></tr>
        <tr><td>Revenue trend (90 vs prior 90 days)</td><td class="n">${pct(b.revenue_trend_90d)}</td><td class="n">—</td></tr>
        <tr><td>Late invoices</td><td class="n">${pct(b.late_invoice_rate)}</td><td class="n">—</td></tr>
        <tr><td>Churn probability</td><td class="n">${pct(b.renewal_risk_score)}</td><td class="n">${pct(rp.region_churn)} / ${pct(rp.portfolio_churn)}</td></tr></tbody></table></div>
      <div class="panel"><h2>Campaign highlights</h2>${hl(o.best_campaign, "Best")}${hl(o.worst_campaign, "Needs attention")}
        <p class="note">${o.genie_questions} question${o.genie_questions === 1 ? "" : "s"} asked from this view. See Ask Genie.</p></div>
    </div>
    <p class="note">Scored by the registered champion model ${esc((b.model_uri || "").split("/").pop())} on ${esc(String(b.scored_at).slice(0, 10))}. Synthetic data.</p>`;
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
  document.querySelectorAll(".viewcol").forEach((c) => (c.hidden = !operator));
  try {
    const rows = await api("/v1/genie/history?limit=30");
    $("#histcount").textContent = operator ? `(all views, ${rows.length} most recent)` : `(asked from the ${esc($("#key").selectedOptions[0].textContent)} view)`;
    body.innerHTML = rows.length ? rows.map((r) => `<tr><td>${esc(r.ts.slice(0, 19).replace("T", " "))}</td>${operator ? `<td><span class="tag">${esc(r.view || "—")}</span></td>` : ""}<td>${esc(r.asked_by || "—")}</td>
      <td>${esc(r.question)}${r.genie_url ? ` <a href="${esc(r.genie_url)}" target="_blank" rel="noopener">conversation</a>` : ""}</td>
      <td>${r.intent ? `<span class="tag">${esc(r.intent)}</span>` : ""}</td><td class="n">${esc(r.duration_ms)}</td>
      <td>${r.status === 200 ? '<span class="tag ok">answered</span>' : `<span class="tag bad" title="${esc(r.error)}">failed</span>`}</td></tr>`).join("")
      : `<tr><td colspan="${operator ? 7 : 6}" class="note">No questions asked from this view yet.</td></tr>`;
  } catch (e) { body.innerHTML = `<tr><td colspan="7" class="err">${esc(e.message)}</td></tr>`; }
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
  const operator = isPortfolio();
  $("#runtitle").textContent = operator ? "Latest orchestration run" : "How fresh is your data";
  $("#reqtitle").textContent = operator ? "Recent requests" : "Your recent API calls";
  try {
    const r = await api("/v1/pipeline/last-run");
    if (operator) {
      run.innerHTML = `<p class="note">Run <a href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.run_id)}</a>: <span class="tag ${r.result === "SUCCESS" ? "ok" : "bad"}">${esc(r.result)}</span> ${r.total_seconds}s end to end</p>
        <table><thead><tr><th>Task</th><th>Result</th><th class="n">Seconds</th></tr></thead><tbody>${r.tasks.map((t) => `<tr><td>${esc(t.task)}</td><td>${esc(t.result)}</td><td class="n">${t.seconds}</td></tr>`).join("")}</tbody></table>`;
    } else {
      const o = await api(`/v1/brands/${brandId()}/overview`);
      const done = r.finished_at_ms ? new Date(r.finished_at_ms).toLocaleString() : "unknown";
      run.innerHTML = `<div class="cards flat">
        ${card("", "Last refresh of your data", esc(done), `<span class="tag ${r.result === "SUCCESS" ? "ok" : "bad"}">${esc(r.result)}</span> full run took ${r.total_seconds}s`)}
        ${card("", "Risk score computed", esc(String(o.brand.scored_at).slice(0, 16).replace("T", " ")), esc((o.brand.model_uri || "").split("/").pop()))}
        ${card("", "Served from", "Lakebase", "Single-digit-millisecond reads for your brand portal")}</div>`;
    }
    const rows = await api("/v1/telemetry/recent");
    body.innerHTML = rows.map((x) => `<tr><td>${esc(x.ts.slice(11, 19))}</td><td>${esc(x.method)} ${esc(x.route)}</td><td class="n">${x.status}</td><td class="n">${esc(x.duration_ms)}</td><td>${esc(x.key_label || "")}</td></tr>`).join("") || '<tr><td colspan="5" class="note">No calls yet.</td></tr>';
  } catch (e) { fail(run, e); }
}

roleHint();
outcome();
