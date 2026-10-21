// Traackr Influencer Revenue API — developer docs / playground
(() => {
  const state = { keys: [], brands: [], selectedKey: null };

  // ---------- nav ----------
  function showSection(id) {
    document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
    document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
    const target = document.getElementById(id);
    if (target) target.classList.add('active');
    document.querySelectorAll(`[data-target="${id}"]`).forEach(l => l.classList.add('active'));
    if (id === 'admin-keys') loadAdminKeys();
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }
  document.querySelectorAll('[data-target]').forEach(el => {
    el.addEventListener('click', (e) => {
      e.preventDefault();
      showSection(el.dataset.target);
      history.replaceState(null, '', '#' + el.dataset.target);
    });
  });
  const hash = location.hash.replace('#', '');
  if (hash) showSection(hash);

  // ---------- key picker (sidebar) ----------
  function describeKey(k) {
    if (k.brand_scope === 'all') return '★ All brands';
    if (k.brand_scope === 'brand_name') return `${k.brand_id} · ${k.accounts.length} account${k.accounts.length === 1 ? '' : 's'}`;
    if (k.brand_scope === 'account_id') return `${k.brand_id}`;
    return k.brand_id || '?';
  }

  async function loadKeys() {
    const sel = document.getElementById('key-select');
    try {
      const res = await fetch('/v1/admin/api-keys');
      if (!res.ok) throw new Error(res.status + ' ' + res.statusText);
      const data = await res.json();
      state.keys = data.keys || [];
      sel.innerHTML = '';
      if (state.keys.length === 0) {
        sel.innerHTML = '<option value="">(no keys)</option>';
      }
      for (const k of state.keys) {
        const opt = document.createElement('option');
        opt.value = k.api_key;
        const tag = k.is_active ? '' : ' [REVOKED]';
        opt.textContent = `${k.api_key} — ${describeKey(k)}${tag}`;
        opt.disabled = !k.is_active;
        sel.appendChild(opt);
      }
      const firstActive = state.keys.find(k => k.is_active);
      if (firstActive) {
        sel.value = firstActive.api_key;
        state.selectedKey = firstActive;
        updateKeyMeta();
      }
    } catch (e) {
      sel.innerHTML = '<option value="">(failed to load)</option>';
      console.error('Failed to load keys', e);
    }
  }
  function updateKeyMeta() {
    const k = state.selectedKey;
    const meta = document.getElementById('key-meta');
    if (!k) { meta.textContent = ''; return; }
    if (k.brand_scope === 'all') {
      meta.innerHTML = `Scope: <b>All brands</b> · ${k.rate_limit_per_min} req/min`;
    } else if (k.brand_scope === 'brand_name') {
      const ids = (k.accounts || []).map(a => a.account_id).slice(0, 4).join(', ');
      const more = k.accounts.length > 4 ? `, +${k.accounts.length - 4} more` : '';
      meta.innerHTML = `Brand: <b>${escapeHtml(k.brand_id)}</b> · ${k.accounts.length} account(s) · ${k.rate_limit_per_min} req/min<br><span class="muted">${escapeHtml(ids + more)}</span>`;
    } else {
      meta.innerHTML = `Account: <b>${escapeHtml(k.brand_id)}</b> · ${k.rate_limit_per_min} req/min`;
    }
    // Auto-fill the first valid brand_id into the Try-it forms.
    const firstId = k.brand_scope === 'all'
      ? (state.brands[0] && state.brands[0].account_ids[0]) || 'ACC-00001'
      : (k.accounts[0] && k.accounts[0].account_id) || '';
    if (firstId) {
      document.querySelectorAll('input[name="brand_id"]').forEach(el => el.value = firstId);
    }
  }
  document.getElementById('key-select').addEventListener('change', (e) => {
    state.selectedKey = state.keys.find(k => k.api_key === e.target.value) || null;
    updateKeyMeta();
  });

  // ---------- Try it ----------
  function buildUrl(endpointKey, form) {
    const data = Object.fromEntries(new FormData(form).entries());
    if (endpointKey === 'renewal-health') return `/v1/brands/${encodeURIComponent(data.brand_id)}/renewal-health`;
    if (endpointKey === 'campaigns') {
      const qs = new URLSearchParams({ status: data.status, limit: data.limit });
      return `/v1/brands/${encodeURIComponent(data.brand_id)}/campaigns?${qs}`;
    }
    if (endpointKey === 'creators') {
      const qs = new URLSearchParams({ status: data.status, limit: data.limit });
      return `/v1/brands/${encodeURIComponent(data.brand_id)}/creators?${qs}`;
    }
    if (endpointKey === 'creator-by-id') return `/v1/creators/${encodeURIComponent(data.creator_id)}`;
    if (endpointKey === 'campaign-by-id') return `/v1/campaigns/${encodeURIComponent(data.campaign_id)}`;
    if (endpointKey === 'freshness') return '/v1/freshness';
    return '';
  }
  document.querySelectorAll('.try-it').forEach(panel => {
    const btn = panel.querySelector('button.run');
    btn.addEventListener('click', async () => {
      const endpoint = panel.dataset.endpoint;
      const section = panel.closest('.endpoint');
      const auth = section.dataset.auth;
      const form = document.createElement('form');
      panel.querySelectorAll('.form input, .form select').forEach(i => form.appendChild(i.cloneNode(true)));
      const url = buildUrl(endpoint, form);

      const responseBox = panel.querySelector('.response');
      responseBox.innerHTML = '<div class="status">Sending…</div><pre>…</pre>';
      responseBox.className = 'response';

      const headers = { 'Accept': 'application/json' };
      if (auth === 'key') {
        if (!state.selectedKey) {
          responseBox.classList.add('bad');
          responseBox.innerHTML = '<div class="status">No API key selected. Pick one in the sidebar.</div>';
          return;
        }
        headers['X-Brand-API-Key'] = state.selectedKey.api_key;
      }

      const t0 = performance.now();
      try {
        const res = await fetch(url, { headers });
        const elapsed = (performance.now() - t0).toFixed(0);
        const text = await res.text();
        let body = text;
        try { body = JSON.stringify(JSON.parse(text), null, 2); } catch {}
        responseBox.className = 'response ' + (res.ok ? 'ok' : 'bad');
        const reqLine = `${res.ok ? '✓' : '✗'} ${res.status} ${res.statusText} · ${elapsed}ms · GET ${url}`;
        responseBox.innerHTML = `<div class="status">${reqLine}</div><pre><code>${escapeHtml(body)}</code></pre>`;
      } catch (e) {
        responseBox.className = 'response bad';
        responseBox.innerHTML = `<div class="status">network error</div><pre>${escapeHtml(String(e))}</pre>`;
      }
    });
  });

  function escapeHtml(s) {
    return String(s).replace(/[&<>"]/g, c => ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;' }[c]));
  }

  // ---------- KPIs ----------
  async function loadKpis() {
    try {
      const response = await fetch('/v1/admin/overview');
      if (!response.ok) throw new Error(response.status);
      const data = await response.json();
      document.getElementById('kpi-brands').textContent = Number(data.brands).toLocaleString();
      document.getElementById('kpi-campaigns').textContent = Number(data.campaigns).toLocaleString();
      document.getElementById('kpi-creators').textContent = Number(data.creators).toLocaleString();
      document.getElementById('kpi-lag').textContent = 'Lakebase';
      document.getElementById('freshness-pill').textContent = 'Lakebase online';
      document.getElementById('freshness-pill').className = 'pill ok';
    } catch {
      document.getElementById('freshness-pill').textContent = 'Lakebase error';
      document.getElementById('freshness-pill').className = 'pill bad';
    }
  }

  // ---------- Admin table ----------
  async function loadAdminKeys() {
    const tbody = document.querySelector('#keys-table tbody');
    tbody.innerHTML = '<tr><td colspan="8" class="muted">Loading…</td></tr>';
    try {
      const res = await fetch('/v1/admin/api-keys');
      if (!res.ok) throw new Error(res.status);
      const data = await res.json();
      state.keys = data.keys || [];
      tbody.innerHTML = '';
      for (const k of state.keys) {
        const tr = document.createElement('tr');
        const lastUsed = k.last_used_at ? new Date(k.last_used_at).toLocaleString() : '—';

        let scopeBadge, brandCell;
        if (k.brand_scope === 'all') {
          scopeBadge = '<span class="pill all-scope">★ All brands</span>';
          brandCell = '<span class="muted">Any account_id allowed</span>';
        } else if (k.brand_scope === 'brand_name') {
          scopeBadge = '<span class="pill name-scope">brand_name</span>';
          const ids = (k.accounts || []).map(a => a.account_id).join(', ');
          brandCell = `<div><b>${escapeHtml(k.brand_id)}</b></div><div class="muted" style="font-size:11px">${escapeHtml(ids)}</div>`;
        } else {
          scopeBadge = '<span class="pill account-scope">account_id</span>';
          const acc = (k.accounts || [])[0] || {};
          brandCell = `<div><b>${escapeHtml(acc.brand_name || k.brand_id)}</b></div><div class="muted" style="font-size:11px">${escapeHtml(k.brand_id)}</div>`;
        }

        tr.innerHTML = `
          <td><code>${escapeHtml(k.api_key)}</code></td>
          <td>${scopeBadge}</td>
          <td>${brandCell}</td>
          <td>${escapeHtml(k.label || '')}</td>
          <td><button class="toggle-btn ${k.is_active ? '' : 'off'}" data-key="${escapeHtml(k.api_key)}" data-state="${k.is_active}">${k.is_active ? 'Active' : 'Revoked'}</button></td>
          <td>${k.rate_limit_per_min}</td>
          <td>${k.use_count}</td>
          <td>${lastUsed}</td>
        `;
        tbody.appendChild(tr);
      }
      tbody.querySelectorAll('.toggle-btn').forEach(btn => btn.addEventListener('click', toggleKey));
    } catch (e) {
      tbody.innerHTML = `<tr><td colspan="8" class="muted">Error: ${e}</td></tr>`;
    }
  }
  async function toggleKey(e) {
    const btn = e.currentTarget;
    const key = btn.dataset.key;
    const currentlyActive = btn.dataset.state === 'true';
    btn.disabled = true;
    try {
      const res = await fetch(`/v1/admin/api-keys/${encodeURIComponent(key)}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_active: !currentlyActive }),
      });
      if (!res.ok) throw new Error(await res.text());
      await loadAdminKeys();
      await loadKeys();
    } catch (err) {
      alert('Toggle failed: ' + err);
    } finally {
      btn.disabled = false;
    }
  }
  document.getElementById('refresh-keys').addEventListener('click', loadAdminKeys);

  // ---------- Create-key modal ----------
  const modal = document.getElementById('key-modal');
  const ckForm = document.getElementById('create-key-form');
  const ckResult = document.getElementById('ck-result');
  const ckBrand = document.getElementById('ck-brand');
  const ckHelp = document.getElementById('ck-brand-help');

  async function loadBrandsIntoSelect() {
    ckBrand.innerHTML = '<option value="">Loading…</option>';
    try {
      const res = await fetch('/v1/admin/brands');
      if (!res.ok) throw new Error(res.status);
      const data = await res.json();
      state.brands = data.brands || [];
      ckBrand.innerHTML = '';

      const allOpt = document.createElement('option');
      allOpt.value = '__ALL__';
      allOpt.dataset.scope = 'all';
      allOpt.textContent = '★ All brands (unrestricted)';
      ckBrand.appendChild(allOpt);

      const sep = document.createElement('option');
      sep.disabled = true;
      sep.textContent = '──────────';
      ckBrand.appendChild(sep);

      for (const b of state.brands) {
        const opt = document.createElement('option');
        opt.value = b.brand_name;
        opt.dataset.scope = 'brand_name';
        opt.dataset.accounts = b.account_ids.join(',');
        const tag = b.account_count > 1 ? ` (${b.account_count} accounts)` : '';
        opt.textContent = `${b.brand_name}${tag}`;
        ckBrand.appendChild(opt);
      }
      updateBrandHelp();
    } catch (e) {
      ckBrand.innerHTML = `<option value="">Failed to load: ${e}</option>`;
    }
  }

  function updateBrandHelp() {
    const opt = ckBrand.options[ckBrand.selectedIndex];
    if (!opt || opt.disabled) { ckHelp.innerHTML = ''; return; }
    if (opt.dataset.scope === 'all') {
      ckHelp.innerHTML = 'Key will accept any <code>brand_id</code> in <code>GET /v1/brands/{id}/&hellip;</code> — useful for internal back-office portals.';
    } else {
      const ids = (opt.dataset.accounts || '').split(',').filter(Boolean);
      const idList = ids.slice(0, 6).map(i => `<code>${escapeHtml(i)}</code>`).join(', ');
      const more = ids.length > 6 ? `, +${ids.length - 6} more` : '';
      ckHelp.innerHTML = `Key grants access to <b>${ids.length}</b> account${ids.length === 1 ? '' : 's'} sharing the name <b>${escapeHtml(opt.value)}</b>: ${idList}${more}`;
    }
  }
  ckBrand.addEventListener('change', updateBrandHelp);

  function openModal() {
    ckForm.reset();
    document.getElementById('ck-active').checked = true;
    ckResult.textContent = '';
    ckResult.className = 'modal-result';
    modal.hidden = false;
    loadBrandsIntoSelect();
    setTimeout(() => document.getElementById('ck-label').focus(), 50);
  }
  function closeModal() { modal.hidden = true; }

  document.getElementById('new-key').addEventListener('click', openModal);
  modal.addEventListener('click', (e) => { if (e.target.dataset.close === '1') closeModal(); });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !modal.hidden) closeModal(); });

  document.getElementById('ck-generate').addEventListener('click', () => {
    const opt = ckBrand.options[ckBrand.selectedIndex];
    let slug = 'brand';
    if (opt && opt.dataset.scope === 'all') slug = 'all';
    else if (opt && opt.value) slug = opt.value.toLowerCase().replace(/[^a-z0-9]/g, '').slice(0, 24);
    const rand = Array.from(crypto.getRandomValues(new Uint8Array(4))).map(b => b.toString(16).padStart(2,'0')).join('');
    document.getElementById('ck-key').value = `pk_demo_${slug || 'brand'}_${rand}`;
  });

  ckForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const opt = ckBrand.options[ckBrand.selectedIndex];
    if (!opt || !opt.value || opt.disabled) {
      ckResult.className = 'modal-result bad';
      ckResult.textContent = 'Pick a brand (or "All brands").';
      return;
    }
    const scope = opt.dataset.scope;
    const fd = new FormData(ckForm);
    const body = {
      brand_scope: scope,
      brand_id: scope === 'all' ? null : opt.value,
      label: fd.get('label'),
      api_key: (fd.get('api_key') || '').toString().trim() || null,
      rate_limit_per_min: parseInt(fd.get('rate_limit_per_min'), 10) || 60,
      is_active: document.getElementById('ck-active').checked,
    };
    const exp = fd.get('expires_at');
    if (exp) body.expires_at = new Date(exp).toISOString();
    if (!body.api_key) delete body.api_key;
    if (body.brand_id == null) delete body.brand_id;

    ckResult.className = 'modal-result';
    ckResult.textContent = 'Creating…';

    try {
      const res = await fetch('/v1/admin/api-keys', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const text = await res.text();
      let payload; try { payload = JSON.parse(text); } catch { payload = text; }
      if (!res.ok) {
        ckResult.className = 'modal-result bad';
        ckResult.innerHTML = `Error ${res.status}: ${escapeHtml(payload.detail || text)}`;
        return;
      }
      ckResult.className = 'modal-result ok';
      const accs = (payload.accounts || []).map(a => `<code>${escapeHtml(a.account_id)}</code>`).join(', ') || '<i>any</i>';
      ckResult.innerHTML = `Created <code>${escapeHtml(payload.key.api_key)}</code><br>Scope: <b>${escapeHtml(payload.key.brand_scope)}</b>${payload.key.brand_id ? ` · ${escapeHtml(payload.key.brand_id)}` : ''}<br>Grants: ${accs}<pre>${escapeHtml(JSON.stringify(payload.key, null, 2))}</pre>`;
      await loadAdminKeys();
      await loadKeys();
    } catch (err) {
      ckResult.className = 'modal-result bad';
      ckResult.textContent = 'Network error: ' + err;
    }
  });

  // ---------- Architecture diagram ----------
  const ICON_GLYPHS = {
    inputData: '⤓',
    lakeflowConnect: '🔌',
    deltaTable: '◆',
    streaming: '▶',
    metricViews: '∑',
    lakebase: '🐘',
    databricksApps: '🚀',
    businessUser: '👤',
  };
  const BAR_TIERS = {
    orchestration: { color: '#f0c419', label: 'Lakeflow Jobs' },
    governance:    { color: '#9b8cff', label: 'Unity Catalog' },
  };

  let archRendered = false;
  async function renderArchitecture() {
    const root = document.getElementById('arch-diagram');
    const legend = document.getElementById('arch-legend');
    if (!root) return;
    if (archRendered) { drawArchEdges(); return; }
    root.innerHTML = '<div class="muted">Loading architecture…</div>';
    let spec;
    try {
      const res = await fetch('/static/architecture.json');
      if (!res.ok) throw new Error(res.status);
      spec = await res.json();
    } catch (e) {
      root.innerHTML = `<div class="muted">Failed to load architecture.json: ${e}</div>`;
      return;
    }
    document.getElementById('arch-title').textContent = spec.name || 'How it works';
    const subEl = document.querySelector('#architecture .lede');
    if (subEl && spec.subtitle) subEl.textContent = spec.subtitle;

    const L = spec.layout || { width: 1700, height: 580, node_width: 200, node_height: 64 };
    const NW = L.node_width, NH = L.node_height;

    root.innerHTML = '';

    // Inner stage at native dimensions; scales to container width via CSS.
    const stage = document.createElement('div');
    stage.className = 'arch-stage';
    stage.style.width = L.width + 'px';
    stage.style.height = L.height + 'px';
    root.appendChild(stage);

    // SVG for edges (same coordinate system as stage)
    const svgNS = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(svgNS, 'svg');
    svg.setAttribute('class', 'arch-edges');
    svg.setAttribute('viewBox', `0 0 ${L.width} ${L.height}`);
    svg.setAttribute('width', L.width);
    svg.setAttribute('height', L.height);
    const defs = document.createElementNS(svgNS, 'defs');
    defs.innerHTML = `<marker id="arrowhead" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="rgba(231,236,255,0.55)"/></marker>`;
    svg.appendChild(defs);
    stage.appendChild(svg);

    // Group bands (e.g., SDP Pipeline (DAB)) — rendered behind nodes
    for (const g of (spec.groups || [])) {
      const band = document.createElement('div');
      band.className = 'arch-group';
      band.style.left = g.x + 'px';
      band.style.top = g.y + 'px';
      band.style.width = g.width + 'px';
      band.style.height = g.height + 'px';
      band.innerHTML = `<span>${escapeHtml(g.label)}</span>`;
      stage.appendChild(band);
    }

    // Foundation bars
    for (const b of (spec.bars || [])) {
      const bar = document.createElement('div');
      const meta = BAR_TIERS[b.tier] || { color: 'var(--border)' };
      bar.className = `arch-bar tier-bar-${b.tier || 'default'}`;
      bar.style.left = b.x + 'px';
      bar.style.top = b.y + 'px';
      bar.style.width = b.width + 'px';
      bar.style.height = (b.height || 34) + 'px';
      bar.style.setProperty('--bar-color', meta.color);
      bar.textContent = b.label;
      stage.appendChild(bar);
    }

    // Nodes
    const nodePositions = {};
    for (const n of spec.nodes) {
      const card = document.createElement('div');
      card.className = `arch-node tier-${n.tier}`;
      card.dataset.id = n.id;
      card.style.left = n.x + 'px';
      card.style.top = n.y + 'px';
      card.style.width = (n.width || NW) + 'px';
      card.style.height = (n.height || NH) + 'px';
      const glyph = ICON_GLYPHS[n.icon] || '●';
      card.innerHTML = `
        <div class="arch-icon" aria-hidden="true">${glyph}</div>
        <div class="arch-text">
          <div class="arch-label">${escapeHtml(n.label)}</div>
          ${n.desc ? `<div class="arch-desc">${escapeHtml(n.desc)}</div>` : ''}
        </div>
      `;
      stage.appendChild(card);
      nodePositions[n.id] = { x: n.x, y: n.y, w: n.width || NW, h: n.height || NH, el: card };
    }

    // Draw edges (uses position metadata, not getBoundingClientRect — so scaling is irrelevant)
    drawArchEdgesAbs(spec, nodePositions, svg);

    // Auto-scale stage to fit container width
    const fit = () => {
      const wrapW = root.clientWidth - 32; // padding
      const scale = Math.min(1, wrapW / L.width);
      stage.style.transform = `scale(${scale})`;
      stage.style.transformOrigin = 'top left';
      // The wrapper height shrinks to the scaled stage height
      root.style.height = (L.height * scale + 28) + 'px';
    };
    fit();
    if (!window._archResizeBound) {
      window._archResizeBound = true;
      window.addEventListener('resize', () => { if (archRendered) fit(); });
    }

    renderLegend(legend);
    archRendered = true;
    window._archSpec = spec;
    window._archNodes = nodePositions;
  }

  function drawArchEdgesAbs(spec, nodes, svg) {
    const NS = 'http://www.w3.org/2000/svg';

    // Decide per-edge entry/exit sides
    function anchor(side, n) {
      switch (side) {
        case 'right':  return { x: n.x + n.w,       y: n.y + n.h / 2 };
        case 'left':   return { x: n.x,             y: n.y + n.h / 2 };
        case 'top':    return { x: n.x + n.w / 2,   y: n.y };
        case 'bottom': return { x: n.x + n.w / 2,   y: n.y + n.h };
      }
    }

    // Track label placements to avoid overlap
    const placed = [];

    for (const e of (spec.edges || [])) {
      const a = nodes[e.from], b = nodes[e.to];
      if (!a || !b) continue;

      // Pick anchors: prefer horizontal flow (right→left). If columns are the same,
      // use top/bottom. If destination is above, exit top; below, exit bottom.
      let from, to;
      if (b.x > a.x + a.w / 2) {
        from = anchor('right', a);
        to = anchor('left', b);
      } else if (b.x + b.w < a.x + a.w / 2) {
        from = anchor('left', a);
        to = anchor('right', b);
      } else if (b.y > a.y) {
        from = anchor('bottom', a);
        to = anchor('top', b);
      } else {
        from = anchor('top', a);
        to = anchor('bottom', b);
      }

      // Cubic Bezier with horizontal lean (or vertical, depending on dominant axis)
      const horizontal = Math.abs(to.x - from.x) >= Math.abs(to.y - from.y);
      let c1, c2;
      if (horizontal) {
        const dx = Math.max(40, Math.abs(to.x - from.x) * 0.55);
        c1 = { x: from.x + Math.sign(to.x - from.x) * dx, y: from.y };
        c2 = { x: to.x   - Math.sign(to.x - from.x) * dx, y: to.y };
      } else {
        const dy = Math.max(40, Math.abs(to.y - from.y) * 0.55);
        c1 = { x: from.x, y: from.y + Math.sign(to.y - from.y) * dy };
        c2 = { x: to.x,   y: to.y   - Math.sign(to.y - from.y) * dy };
      }

      const path = document.createElementNS(NS, 'path');
      const d = `M ${from.x},${from.y} C ${c1.x},${c1.y} ${c2.x},${c2.y} ${to.x},${to.y}`;
      path.setAttribute('d', d);
      path.setAttribute('class', 'arch-edge' + (e.animated ? ' animated' : ''));
      path.setAttribute('marker-end', 'url(#arrowhead)');
      svg.appendChild(path);

      if (e.label) {
        // Midpoint of the cubic Bezier at t=0.5
        const mx = 0.125 * from.x + 0.375 * c1.x + 0.375 * c2.x + 0.125 * to.x;
        const my = 0.125 * from.y + 0.375 * c1.y + 0.375 * c2.y + 0.125 * to.y;
        // Nudge if near a previous label
        let dy = 0;
        for (const p of placed) {
          if (Math.abs(p.x - mx) < 80 && Math.abs(p.y - (my + dy)) < 18) dy -= 22;
        }
        const cx = mx, cy = my + dy;
        placed.push({ x: cx, y: cy });

        const text = document.createElementNS(NS, 'text');
        text.setAttribute('x', cx);
        text.setAttribute('y', cy);
        text.setAttribute('class', 'arch-edge-label');
        text.setAttribute('text-anchor', 'middle');
        text.setAttribute('dominant-baseline', 'middle');
        text.textContent = e.label;
        svg.appendChild(text);
        const tb = text.getBBox();
        const padX = 6, padY = 3;
        const rectEl = document.createElementNS(NS, 'rect');
        rectEl.setAttribute('x', tb.x - padX);
        rectEl.setAttribute('y', tb.y - padY);
        rectEl.setAttribute('width', tb.width + 2 * padX);
        rectEl.setAttribute('height', tb.height + 2 * padY);
        rectEl.setAttribute('class', 'arch-edge-label-bg');
        rectEl.setAttribute('rx', 4); rectEl.setAttribute('ry', 4);
        svg.insertBefore(rectEl, text);
      }
    }
  }

  function drawArchEdges() { /* no-op: replaced by drawArchEdgesAbs (absolute layout) */ }

  function renderLegend(box) {
    if (!box) return;
    const items = [
      ['Source system', 'source'],
      ['Ingest', 'ingest'],
      ['Bronze', 'bronze'],
      ['Silver / Gold', 'gold'],
      ['Platinum (streaming + AUTO CDC)', 'streaming'],
      ['Lakebase (Postgres)', 'compute'],
      ['Customer-facing API', 'analytics'],
      ['Users', 'consumer'],
    ];
    box.innerHTML = items.map(([label, tier]) =>
      `<div class="legend-item"><span class="legend-swatch tier-${tier}"></span>${escapeHtml(label)}</div>`
    ).join('');
  }

  // Hook the architecture render into showSection
  const _origShowSection = showSection;
  showSection = function(id) {
    _origShowSection(id);
    if (id === 'architecture') renderArchitecture();
    if (id === 'propagation') initPropagationTab();
    if (id === 'ai-insights') loadAiInsights();
    if (id === 'genie') initGenie();
    if (id === 'bundle') initBundleTab();
  };
  if (location.hash === '#architecture') renderArchitecture();
  if (location.hash === '#propagation') initPropagationTab();
  if (location.hash === '#ai-insights') loadAiInsights();
  if (location.hash === '#genie') initGenie();
  if (location.hash === '#bundle') initBundleTab();

  let aiInsightsLoaded = false;
  async function loadAiInsights() {
    if (aiInsightsLoaded) return;
    const stateBox = document.getElementById('ai-insight-state');
    const grid = document.getElementById('ai-insight-grid');
    stateBox.textContent = 'Loading governed recommendations…';
    try {
      const response = await fetch('/v1/ai-insights');
      if (!response.ok) throw new Error(`${response.status}: ${await response.text()}`);
      const payload = await response.json();
      const rows = payload.insights || [];
      if (!rows.length) {
        stateBox.textContent = 'No recommendations are available. Run the orchestration job to generate them.';
        return;
      }
      grid.innerHTML = rows.map(row => `
        <article class="insight-card">
          <div class="insight-card-head">
            <div><div class="insight-brand">${escapeHtml(row.brand_name)}</div><h3>${escapeHtml(row.campaign_name)}</h3></div>
            <div class="insight-roi">${Number(row.roi).toFixed(2)}× ROI</div>
          </div>
          <div class="insight-metrics"><span>$${Number(row.total_spend_usd).toLocaleString()} spend</span><span>$${Number(row.total_revenue_usd).toLocaleString()} revenue</span></div>
          <p>${escapeHtml(row.recommendation)}</p>
          <div class="insight-meta">${escapeHtml(row.model_function)} · ${escapeHtml(row.generated_at)}</div>
        </article>`).join('');
      stateBox.textContent = `${rows.length} recommendations · ${payload.source}`;
      aiInsightsLoaded = true;
    } catch (error) {
      stateBox.textContent = `Unable to load AI recommendations: ${error}`;
    }
  }

  let genieInitialized = false;
  const genieAgentUrl = 'https://dbc-01f27b97-0e2e.cloud.databricks.com/genie/rooms/01f1cbfef7e81a1d8d9161f8fd8d65f6?o=7474653524978634';
  function initGenie() {
    if (genieInitialized) return;
    genieInitialized = true;
    fetch('/v1/genie/whoami').then(r => r.json()).then(data => {
      document.getElementById('genie-identity').textContent = `Signed in as ${data.user}`;
    });
    document.querySelectorAll('.genie-sample').forEach(button => button.addEventListener('click', () => {
      document.getElementById('genie-question').value = button.textContent;
    }));
    document.getElementById('genie-send').addEventListener('click', askGenie);
  }

  async function askGenie() {
    const input = document.getElementById('genie-question');
    const statusBox = document.getElementById('genie-status');
    const answerBox = document.getElementById('genie-answer');
    const sqlBox = document.getElementById('genie-sql');
    const question = input.value.trim();
    if (!question) return;
    statusBox.innerHTML = `Genie is analyzing governed sources and generating SQL… <a href="${genieAgentUrl}" target="_blank" rel="noopener">Open Genie conversation ↗</a>`;
    answerBox.hidden = true;
    sqlBox.hidden = true;
    try {
      const response = await fetch('/v1/genie/ask', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({question})});
      if (!response.ok) throw new Error(`${response.status}: ${await response.text()}`);
      const payload = await response.json();
      answerBox.innerHTML = `<p>${escapeHtml(payload.answer).replaceAll('\n', '<br>')}</p><div class="insight-meta">${escapeHtml(payload.disclaimer)} · Conversation ${escapeHtml(payload.conversation_id)} · <a href="${escapeHtml(payload.genie_url)}" target="_blank" rel="noopener">Open in Genie ↗</a></div>`;
      answerBox.hidden = false;
      if (payload.api_script) {
        sqlBox.querySelector('h3').textContent = 'API script';
        sqlBox.querySelector('code').textContent = payload.api_script;
        sqlBox.hidden = false;
      } else if ((payload.queries || []).length) {
        sqlBox.querySelector('h3').textContent = 'Generated SQL';
        sqlBox.querySelector('code').textContent = payload.queries.map(query => query.sql).join('\n\n');
        sqlBox.hidden = false;
      }
      statusBox.innerHTML = `Completed · ${payload.queries.length} generated query${payload.queries.length === 1 ? '' : 'ies'} · <a href="${escapeHtml(payload.genie_url)}" target="_blank" rel="noopener">Open Genie conversation ↗</a>`;
    } catch (error) {
      statusBox.innerHTML = `Genie error: ${escapeHtml(String(error))} · <a href="${genieAgentUrl}" target="_blank" rel="noopener">Open Genie ↗</a>`;
    }
  }

  // ---------- Live Change Propagation ----------
  const PROP_WS = {
    host:  'https://dbc-01f27b97-0e2e.cloud.databricks.com',
    orgId: '7474653524978634',
    sdpPipelineId: '6bafb573-8965-4f9e-bf4e-c8f7e06a9872',
    syncPipelineId: {
      creator:  '77b1d73b-9668-49d4-bd33-29a52e9de4d6',
      campaign: '195d467e-82c9-4aba-b832-4d7f5b97ea45',
    },
    cdcVolumePath: 'at_10526_workspace/influencer_engagement_fe_bar/cdc_events',
    // Lakebase legacy Database Instance: "instance" is the project, "database" is the
    // logical-database (Lakebase autoscale's "branch" analogue).
    lakebaseInstance: 'influencer-fe-bar-lb',
    lakebaseDatabase: 'influencer_fe_bar',
  };
  function sdpUpdateUrl(updateId) {
    if (!updateId) return null;
    return `${PROP_WS.host}/pipelines/${PROP_WS.sdpPipelineId}/updates/${updateId}?o=${PROP_WS.orgId}`;
  }
  function syncUpdateUrl(entity, updateId) {
    if (!updateId) return null;
    const pid = PROP_WS.syncPipelineId[entity];
    return `${PROP_WS.host}/pipelines/${pid}/updates/${updateId}?o=${PROP_WS.orgId}`;
  }
  function cdcVolumeUrl(entity) {
    const sub = entity === 'creator' ? 'creators' : 'campaigns';
    return `${PROP_WS.host}/explore/data/volumes/${PROP_WS.cdcVolumePath}/${sub}?o=${PROP_WS.orgId}`;
  }
  function lakebaseInstanceUrl() {
    return `${PROP_WS.host}/compute/database-instances/${PROP_WS.lakebaseInstance}?o=${PROP_WS.orgId}`;
  }
  function appEndpointUrl(entity, entityId) {
    // Navigate the user to the Try-it section instead of a raw fetch with auth.
    return `#ep-${entity}-by-id`;
  }

  const prop = {
    initialised: false,
    targets: null,        // /v1/admin/propagation/targets response
    activeEntity: 'creator',
    inFlight: false,
    pollHandle: null,
    pollStart: 0,
    lastChange: null,     // { change_id, entity, entity_id, run_id, sync_run_id }
  };

  function activeBrandId() {
    const k = state.selectedKey;
    if (!k) return 'ACC-00001';
    if (k.brand_scope === 'account_id') return k.brand_id;
    if (k.brand_scope === 'brand_name' && k.accounts && k.accounts.length) return k.accounts[0].account_id;
    return 'ACC-00001';
  }

  async function initPropagationTab() {
    if (prop.initialised) {
      // Refresh targets if brand changed
      if (prop._brand !== activeBrandId()) await loadPropTargets();
      return;
    }
    prop.initialised = true;
    // Wire entity toggle
    document.querySelectorAll('#prop-entity-toggle button').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('#prop-entity-toggle button').forEach(b => b.classList.toggle('active', b === btn));
        prop.activeEntity = btn.dataset.val;
        renderEntityOptions();
        renderFieldOptions();
      });
    });
    document.getElementById('prop-entity').addEventListener('change', renderCurrentValue);
    document.getElementById('prop-field').addEventListener('change', () => { renderValueInput(); renderCurrentValue(); });
    document.getElementById('prop-push').addEventListener('click', pushChange);
    await loadPropTargets();
  }

  async function loadPropTargets() {
    const brand = activeBrandId();
    prop._brand = brand;
    const sel = document.getElementById('prop-entity');
    sel.innerHTML = '<option>loading…</option>';
    try {
      const res = await fetch('/v1/admin/propagation/targets?brand_id=' + encodeURIComponent(brand));
      if (!res.ok) throw new Error(res.status);
      prop.targets = await res.json();
      renderEntityOptions();
      renderFieldOptions();
    } catch (e) {
      sel.innerHTML = `<option>failed: ${e}</option>`;
    }
  }

  function renderEntityOptions() {
    const sel = document.getElementById('prop-entity');
    sel.innerHTML = '';
    const list = (prop.targets || {})[prop.activeEntity === 'creator' ? 'creators' : 'campaigns'] || [];
    for (const e of list) {
      const opt = document.createElement('option');
      if (prop.activeEntity === 'creator') {
        opt.value = e.creator_id;
        opt.textContent = `${e.creator_id} — ${e.display_name} (${e.status}, ${e.tier})`;
      } else {
        opt.value = e.campaign_id;
        opt.textContent = `${e.campaign_id} — ${e.name} (${e.status})`;
      }
      sel.appendChild(opt);
    }
    if (list.length === 0) {
      sel.innerHTML = '<option disabled>no entities for this brand</option>';
    }
    renderCurrentValue();
  }

  function renderFieldOptions() {
    const sel = document.getElementById('prop-field');
    const fields = (prop.targets?.allowed_fields || {})[prop.activeEntity] || [];
    sel.innerHTML = '';
    for (const f of fields) {
      const opt = document.createElement('option');
      opt.value = f;
      opt.textContent = f;
      sel.appendChild(opt);
    }
    renderValueInput();
    renderCurrentValue();
  }

  function renderValueInput() {
    const field = document.getElementById('prop-field').value;
    const enumKey = `${prop.activeEntity}.${field}`;
    const allowed = (prop.targets?.allowed_values || {})[enumKey];
    const enumSel = document.getElementById('prop-value-enum');
    const text = document.getElementById('prop-value-text');
    if (allowed && allowed.length) {
      enumSel.hidden = false; text.hidden = true;
      enumSel.innerHTML = '';
      for (const v of allowed) {
        const o = document.createElement('option'); o.value = v; o.textContent = v;
        enumSel.appendChild(o);
      }
    } else {
      enumSel.hidden = true; text.hidden = false;
      text.value = '';
      text.placeholder = field === 'display_name' ? 'e.g. Sofia Live Demo' : (field === 'name' ? 'e.g. Coach Live Capsule' : 'new value');
    }
    document.getElementById('prop-push').disabled = false;
  }

  function getCurrentValue() {
    const entityId = document.getElementById('prop-entity').value;
    const field = document.getElementById('prop-field').value;
    const list = (prop.targets || {})[prop.activeEntity === 'creator' ? 'creators' : 'campaigns'] || [];
    const idKey = prop.activeEntity === 'creator' ? 'creator_id' : 'campaign_id';
    const row = list.find(e => e[idKey] === entityId);
    return row ? row[field] : null;
  }

  function getNewValue() {
    const enumSel = document.getElementById('prop-value-enum');
    return enumSel.hidden ? document.getElementById('prop-value-text').value.trim() : enumSel.value;
  }

  function renderCurrentValue() {
    const cur = getCurrentValue();
    const field = document.getElementById('prop-field').value;
    const el = document.getElementById('prop-current');
    if (cur === null || cur === undefined) { el.textContent = '—'; return; }
    el.innerHTML = `Current <code>${escapeHtml(field)}</code>: <b>${escapeHtml(String(cur))}</b>`;
  }

  function resetTracker() {
    document.querySelectorAll('#prop-tracker .prop-stage').forEach(s => s.dataset.reached = '0');
    document.querySelectorAll('#prop-tracker .prop-edge').forEach(e => e.dataset.active = '0');
    document.querySelectorAll('#prop-tracker .prop-stage-link').forEach(a => a.remove());
    ['raw','bronze','platinum','lakebase','api'].forEach(k => {
      const el = document.querySelector(`#prop-tracker [data-bind="ms-${k}"]`);
      if (el) el.textContent = '';
    });
    document.getElementById('prop-total').textContent = '—';
    document.getElementById('prop-runid').textContent = '—';
    document.getElementById('prop-syncid').textContent = '—';
    document.getElementById('prop-status').textContent = 'in flight';
    document.getElementById('prop-error').hidden = true;
  }

  function renderBefore() {
    const entityId = document.getElementById('prop-entity').value;
    const field = document.getElementById('prop-field').value;
    const list = (prop.targets || {})[prop.activeEntity === 'creator' ? 'creators' : 'campaigns'] || [];
    const idKey = prop.activeEntity === 'creator' ? 'creator_id' : 'campaign_id';
    const row = list.find(e => e[idKey] === entityId);
    const before = document.getElementById('prop-before');
    if (!row) { before.innerHTML = '<code class="muted">entity not found</code>'; return; }
    const j = JSON.stringify(row, null, 2);
    const hi = j.replace(new RegExp(`("${field}":\\s*)("[^"]*"|[^,\\n]+)`),
      (_, k, v) => `${k}<span class="diff-old">${v}</span>`);
    before.innerHTML = `<code>${hi}</code>`;
  }

  async function renderAfter(brandId, entityId, field, newValue) {
    const key = state.selectedKey?.api_key;
    if (!key) return;
    const isCreator = prop.activeEntity === 'creator';
    const path = isCreator
      ? `/v1/brands/${encodeURIComponent(brandId)}/creators?status=all&limit=200`
      : `/v1/brands/${encodeURIComponent(brandId)}/campaigns?status=all&limit=200`;
    try {
      const r = await fetch(path, { headers: { 'X-Brand-API-Key': key } });
      if (!r.ok) throw new Error(r.status);
      const data = await r.json();
      const items = data.creators || data.campaigns || [];
      const idKey = isCreator ? 'creator_id' : 'campaign_id';
      const row = items.find(e => e[idKey] === entityId);
      const after = document.getElementById('prop-after');
      if (!row) { after.innerHTML = '<code class="muted">entity not in current response</code>'; return; }
      const j = JSON.stringify(row, null, 2);
      const hi = j.replace(new RegExp(`("${field}":\\s*)("[^"]*"|[^,\\n]+)`),
        (_, k, v) => `${k}<span class="diff-new">${v}</span>`);
      after.innerHTML = `<code>${hi}</code>`;
    } catch (e) {
      document.getElementById('prop-after').innerHTML = `<code class="muted">refresh failed: ${e}</code>`;
    }
  }

  async function pushChange() {
    if (prop.inFlight) return;
    const entityId = document.getElementById('prop-entity').value;
    const field = document.getElementById('prop-field').value;
    const newValue = getNewValue();
    const cur = getCurrentValue();

    if (!entityId || !field || !newValue) {
      showPropError('pick an entity, field, and new value');
      return;
    }
    if (String(cur) === String(newValue)) {
      showPropError(`new value is identical to current (${cur}); pick a different value`);
      return;
    }
    const brand = activeBrandId();
    prop.inFlight = true;
    const pushBtn = document.getElementById('prop-push');
    pushBtn.disabled = true; pushBtn.classList.add('busy'); pushBtn.textContent = 'Pushing…';
    resetTracker();
    renderBefore();
    document.getElementById('prop-after').innerHTML = '<code class="muted">waiting for propagation…</code>';

    try {
      const res = await fetch('/v1/admin/propagation/changes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ entity: prop.activeEntity, entity_id: entityId, field, new_value: newValue, brand_id: brand }),
      });
      const text = await res.text();
      const payload = (() => { try { return JSON.parse(text); } catch { return { detail: text }; } })();
      if (!res.ok) {
        showPropError(`Error ${res.status}: ${payload.detail || text}`);
        endPush();
        return;
      }
      // Stage "raw" reached immediately on POST success
      markStage('raw', true);
      document.querySelector('.prop-edge[data-from="raw"][data-to="bronze"]').dataset.active = '1';

      // Stash references and render per-stage links (raw + bronze + platinum + api)
      // available immediately; sync-pipeline link uses sync_run_id from the POST payload.
      prop.lastChange = {
        change_id: payload.change_id,
        entity: prop.activeEntity,
        entity_id: entityId,
        run_id: payload.run_id,
        sync_run_id: payload.sync_run_id,
      };
      refreshStageLinks();

      const sdpA = sdpUpdateUrl(payload.run_id);
      document.getElementById('prop-runid').innerHTML = sdpA
        ? `<a href="${sdpA}" target="_blank" rel="noopener" class="run-link">${escapeHtml(payload.run_id || '—')}</a>`
        : (payload.run_id || '—');
      const syncA = syncUpdateUrl(prop.activeEntity, payload.sync_run_id);
      document.getElementById('prop-syncid').innerHTML = syncA
        ? `<a href="${syncA}" target="_blank" rel="noopener" class="run-link">${escapeHtml(payload.sync_run_id || '—')}</a>`
        : (payload.sync_run_id || '—');

      prop.pollStart = Date.now();
      startPolling(payload.change_id, brand, entityId, field, newValue);
    } catch (e) {
      showPropError('network error: ' + e);
      endPush();
    }
  }

  function startPolling(changeId, brand, entityId, field, newValue) {
    if (prop.pollHandle) clearInterval(prop.pollHandle);
    const deadline = Date.now() + 10 * 60 * 1000;
    let lastStages = {};
    let pollInProgress = false;
    let transientFailures = 0;
    const poll = async () => {
      if (pollInProgress) return;
      pollInProgress = true;
      try {
        const r = await fetch(`/v1/admin/propagation/changes/${encodeURIComponent(changeId)}/status`);
        if (!r.ok) {
          if ([502, 503, 504].includes(r.status)) {
            transientFailures += 1;
            document.getElementById('prop-status').textContent = 'app reconnecting';
            if (transientFailures >= 20) {
              showPropError('The app is still restarting. Refresh the page to resume tracking this change.');
            }
            return;
          }
          showPropError(`status check failed (${r.status})`);
          return;
        }
        transientFailures = 0;
        const d = await r.json();
        // Update stage dots / edges
        const keys = ['raw','bronze','platinum','lakebase','api'];
        for (const s of d.stages) {
          if (lastStages[s.key] !== s.reached) {
            markStage(s.key, s.reached);
            lastStages[s.key] = s.reached;
          }
        }
        // Edges: edge from K to next K2 is active when K is reached and K2 is not
        const reached = new Set(d.stages.filter(s => s.reached).map(s => s.key));
        for (const e of document.querySelectorAll('#prop-tracker .prop-edge')) {
          e.dataset.active = (reached.has(e.dataset.from) && !reached.has(e.dataset.to)) ? '1' : '0';
        }
        // Per-stage timings
        const m = d.per_stage_ms || {};
        const fmt = (ms) => ms == null ? '' : (ms < 1000 ? `${ms} ms` : `${(ms/1000).toFixed(1)} s`);
        const set = (k, v) => {
          const el = document.querySelector(`#prop-tracker [data-bind="ms-${k}"]`);
          if (el) el.textContent = v || '';
        };
        set('bronze', fmt(m.bronze));
        set('platinum', fmt(m.platinum));
        set('lakebase', fmt(m.lakebase));
        set('api', fmt(m.api));

        // sync_run_id can change once after auto-retrigger; refresh link + stash
        if (d.sync_run_id && prop.lastChange && d.sync_run_id !== prop.lastChange.sync_run_id) {
          prop.lastChange.sync_run_id = d.sync_run_id;
          const syncA = syncUpdateUrl(prop.lastChange.entity, d.sync_run_id);
          document.getElementById('prop-syncid').innerHTML = syncA
            ? `<a href="${syncA}" target="_blank" rel="noopener" class="run-link">${escapeHtml(d.sync_run_id)}</a>`
            : d.sync_run_id;
          refreshStageLinks();
        }
        document.getElementById('prop-status').textContent =
          d.complete ? 'complete' : (d.sync_retriggered ? 'sync re-triggered' : 'in flight');

        if (d.complete) {
          document.getElementById('prop-total').textContent =
            d.total_ms < 1000 ? `${d.total_ms} ms` : `${(d.total_ms/1000).toFixed(2)} s (${Math.floor(d.total_ms/60000)}m ${Math.round((d.total_ms%60000)/1000)}s)`;
          await renderAfter(brand, entityId, field, newValue);
          endPush();
          return;
        }
        if (Date.now() > deadline) {
          showPropError('timed out after 10 minutes; pipeline may still be running');
          endPush();
        }
      } catch (e) {
        transientFailures += 1;
        document.getElementById('prop-status').textContent = 'app reconnecting';
        if (transientFailures >= 20) {
          showPropError('Unable to reconnect to the app. Refresh the page to resume tracking this change.');
        }
      } finally {
        pollInProgress = false;
      }
    };
    prop.pollHandle = setInterval(poll, 1500);
    poll();
  }

  function markStage(key, reached) {
    const el = document.querySelector(`#prop-tracker .prop-stage[data-key="${key}"]`);
    if (el) el.dataset.reached = reached ? '1' : '0';
  }

  function setStageLinks(stageKey, links) {
    // links: array of {href, label, title} (or null/empty to clear)
    const el = document.querySelector(`#prop-tracker .prop-stage[data-key="${stageKey}"]`);
    if (!el) return;
    el.querySelectorAll('a.prop-stage-link').forEach(a => a.remove());
    for (const l of (links || []).filter(Boolean)) {
      if (!l.href) continue;
      const a = document.createElement('a');
      a.className = 'prop-stage-link';
      a.target = l.href.startsWith('#') ? '_self' : '_blank';
      a.rel = 'noopener';
      a.textContent = (l.label || 'open') + ' ↗';
      a.href = l.href;
      a.title = l.title || '';
      el.appendChild(a);
    }
  }
  // Backwards-compat shim (other callers may still use the single-link signature)
  function setStageLink(stageKey, href, title) {
    setStageLinks(stageKey, [{ href, title }]);
  }

  function refreshStageLinks() {
    const c = prop.lastChange;
    if (!c) return;
    setStageLinks('raw', [
      { href: cdcVolumeUrl(c.entity), label: 'volume',
        title: 'Open the cdc_events volume in Catalog Explorer' },
    ]);
    setStageLinks('bronze', [
      { href: sdpUpdateUrl(c.run_id), label: 'SDP run',
        title: 'Open the SDP pipeline update (bronze + silver + gold + platinum)' },
    ]);
    setStageLinks('platinum', [
      { href: sdpUpdateUrl(c.run_id), label: 'SDP run',
        title: 'Open the SDP pipeline update' },
    ]);
    setStageLinks('lakebase', [
      { href: lakebaseInstanceUrl(), label: 'Lakebase',
        title: `Open the Lakebase instance ${PROP_WS.lakebaseInstance} (database: ${PROP_WS.lakebaseDatabase}). Navigate to schema dev_andrea_tardif_… > synced_${c.entity}s to see the row.` },
      { href: syncUpdateUrl(c.entity, c.sync_run_id), label: 'sync run',
        title: `Open the synced-${c.entity}s pipeline update` },
    ]);
    setStageLinks('api', [
      { href: appEndpointUrl(c.entity, c.entity_id), label: 'Try it',
        title: `Open the direct-lookup Try-it for ${c.entity_id}` },
    ]);
  }

  function endPush() {
    if (prop.pollHandle) { clearInterval(prop.pollHandle); prop.pollHandle = null; }
    prop.inFlight = false;
    const btn = document.getElementById('prop-push');
    btn.disabled = false; btn.classList.remove('busy'); btn.textContent = 'Push change';
  }

  function showPropError(msg) {
    const el = document.getElementById('prop-error');
    el.textContent = msg; el.hidden = false;
  }

  // ---------- Bundle source tab ----------
  const bundle = { initialised: false, items: null, currentPath: null };

  async function initBundleTab() {
    if (bundle.initialised) return;
    bundle.initialised = true;
    const tree = document.getElementById('bundle-tree');
    try {
      const res = await fetch('/v1/admin/bundle/files');
      if (!res.ok) throw new Error(res.status);
      const data = await res.json();
      if (data.error) {
        tree.innerHTML = `<div class="muted">${escapeHtml(data.error)}</div>`;
        return;
      }
      bundle.items = data.items;
      renderBundleTree(data.items);
      const defaultPath = data.default_path || 'README.md';
      const has = data.items.find(i => i.type === 'file' && i.path === defaultPath);
      if (has) openBundleFile(defaultPath);
    } catch (e) {
      tree.innerHTML = `<div class="muted">failed: ${escapeHtml(String(e))}</div>`;
    }
  }

  function _treeNode(name, path) {
    return { name, path, dirs: new Map(), files: [] };
  }

  function renderBundleTree(items) {
    // Build a nested directory tree from the flat file list.
    const root = _treeNode('', '');
    const fileItems = items.filter(i => i.type === 'file');
    for (const it of fileItems) {
      const parts = it.path.split('/');
      let node = root;
      for (let i = 0; i < parts.length - 1; i++) {
        const dir = parts[i];
        if (!node.dirs.has(dir)) {
          node.dirs.set(dir, _treeNode(dir, parts.slice(0, i + 1).join('/')));
        }
        node = node.dirs.get(dir);
      }
      node.files.push({ ...it, name: parts[parts.length - 1] });
    }
    const tree = document.getElementById('bundle-tree');
    tree.innerHTML = '';
    tree.appendChild(renderTreeNode(root, /*isRoot=*/true));
  }

  function renderTreeNode(node, isRoot) {
    const el = document.createElement(isRoot ? 'div' : 'details');
    if (!isRoot) {
      el.className = 'tree-dir';
      // Open the SDP source folders by default for discoverability
      const openByDefault = ['src', 'app'].includes(node.name);
      if (openByDefault) el.open = true;
      const summary = document.createElement('summary');
      summary.innerHTML = `<span class="tree-icon">📁</span><span class="tree-name">${escapeHtml(node.name)}</span>`;
      el.appendChild(summary);
    }
    const dirs = [...node.dirs.values()].sort((a, b) => a.name.localeCompare(b.name));
    for (const d of dirs) el.appendChild(renderTreeNode(d, false));
    const files = node.files.sort((a, b) => a.name.localeCompare(b.name));
    for (const f of files) {
      const a = document.createElement('a');
      a.href = '#bundle';
      a.className = 'tree-file';
      a.dataset.path = f.path;
      a.innerHTML = `<span class="tree-icon">${_fileGlyph(f.ext)}</span><span class="tree-name">${escapeHtml(f.name)}</span>`;
      a.addEventListener('click', (ev) => {
        ev.preventDefault();
        openBundleFile(f.path);
      });
      el.appendChild(a);
    }
    return el;
  }

  function _fileGlyph(ext) {
    if (ext === '.md' || ext === '.markdown') return '📘';
    if (ext === '.py')   return '🐍';
    if (ext === '.sql')  return '📊';
    if (ext === '.yml' || ext === '.yaml') return '⚙️';
    if (ext === '.json') return '📦';
    if (ext === '.js')   return '⚡';
    if (ext === '.css')  return '🎨';
    if (ext === '.html') return '📄';
    if (ext === '.sh')   return '💻';
    if (ext === '.txt')  return '📝';
    return '📄';
  }

  async function openBundleFile(path) {
    const viewer = document.getElementById('bundle-viewer');
    viewer.innerHTML = '<div class="muted">loading…</div>';
    // Visually mark the active file
    document.querySelectorAll('#bundle-tree .tree-file.active').forEach(a => a.classList.remove('active'));
    const a = document.querySelector(`#bundle-tree .tree-file[data-path="${CSS.escape(path)}"]`);
    if (a) a.classList.add('active');
    bundle.currentPath = path;
    try {
      const res = await fetch('/v1/admin/bundle/content?path=' + encodeURIComponent(path));
      if (!res.ok) {
        const t = await res.text();
        viewer.innerHTML = `<div class="muted">${res.status}: ${escapeHtml(t)}</div>`;
        return;
      }
      const d = await res.json();
      const sizeLabel = d.size < 1024 ? `${d.size} B` : `${(d.size/1024).toFixed(1)} KB`;
      let body;
      if (d.html) {
        body = `<div class="bundle-md">${d.html}</div>`;
      } else {
        body = `<pre class="bundle-code"><code class="lang-${escapeHtml(d.language || 'text')}">${escapeHtml(d.text)}</code></pre>`;
      }
      viewer.innerHTML = `
        <div class="bundle-file-header">
          <code class="bundle-file-path">${escapeHtml(d.path)}</code>
          <span class="muted">${escapeHtml(d.language)} · ${sizeLabel}</span>
        </div>
        ${body}
      `;
      viewer.scrollTop = 0;
    } catch (e) {
      viewer.innerHTML = `<div class="muted">error: ${escapeHtml(String(e))}</div>`;
    }
  }

  // ---------- init ----------
  void Promise.allSettled([loadKeys(), loadKpis()]);
})();
