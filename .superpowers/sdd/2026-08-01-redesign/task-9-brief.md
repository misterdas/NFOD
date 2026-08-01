### Task 9: views/verdict.js — money-flow verdict view

**Files:**
- Create: `views/verdict.js`
- Consumes: `NFOD.data.loadMoneyFlow()`, `NFOD.utils`.

**Interfaces:**
- Produces: `NFOD.views.verdict.render(state)` — renders executive banner + Smart Money Score, index rolls, FII/Pro/DII stance, conviction matrix (NIFTY/BANKNIFTY tabs), flow divergence, 4-column breadth. Reads the new nested schema (`verdict`, `participants`, `retail`, `rolls`, `breadth`, `conviction`, `divergence`) AND keeps flat `participant_summary` as fallback.

- [ ] **Step 1: Write verdict.js**

```js
window.NFOD = window.NFOD || {};
NFOD.views = NFOD.views || {};
NFOD.views.verdict = (function () {
  let cached = null;
  function biasCls(b) { return /BULLISH/i.test(b || "") ? "bullish" : /BEARISH/i.test(b || "") ? "bearish" : "neutral"; }

  function execBanner(mf) {
    const v = mf.verdict || {};
    const score = v.score ?? mf.executive_summary?.smart_money_score ?? 0;
    const bias = v.bias || mf.executive_summary?.bias_label || "NEUTRAL";
    return `<section class="verdict-banner">
      <div class="banner-left">
        <div class="banner-row"><span class="badge ${biasCls(bias)}">${bias}</span>
        <span class="banner-title">INSTITUTIONAL MARKET VERDICT</span></div>
        <p class="banner-desc">${v.actionDesc || mf.executive_summary?.action_desc || ""}</p>
      </div>
      <div class="banner-right">
        <div class="score-label">Smart Money Score</div>
        <div class="verdict-gauge ${score > 0 ? "pos-up" : score < 0 ? "pos-down" : ""}">${score > 0 ? "+" : ""}${score}</div>
      </div>
    </section>`;
  }

  function stancePanel(mf) {
    const ps = mf.participant_summary || {};
    const p = mf.participants || {};
    if (!Object.keys(ps).length && !Object.keys(p).length) return `<div class="error-card">No participant data.</div>`;
    const row = (label, val, cls) => `<div class="stat-row"><span class="stat-label">${label}</span>
      <span class="stat-value ${cls || ""}">${val}</span></div>`;
    const fmt = v => NFOD.utils.formatIndianNum(v);
    const fii = p.fii || {};
    const pro = p.pro || {};
    const dii = p.dii || {};
    return `<div class="instrument-block">
      <div class="block-header">FII & Pro Daily Positioning Shift</div>
      <div class="panel-body">
        <div class="section-label fii">FII (Institutional)</div>
        ${row("Call Options Stance", fmt(ps.fii_ce_net_short_change ?? fii.options?.ce?.netShort), "mono")}
        ${row("Put Options Stance", fmt(ps.fii_pe_net_short_change ?? fii.options?.pe?.netShort), "mono")}
        ${row("Futures Net Shift", fmt(ps.fii_fut_net_change ?? fii.futures?.net), "mono")}
        <div class="section-label pro">Pro Desk & Retail</div>
        ${row("Pro Call Net-Short", fmt(ps.pro_ce_net_short_change ?? pro.options?.ce?.netShort), "mono")}
        ${row("Pro Put Net-Short", fmt(ps.pro_pe_net_short_change ?? pro.options?.pe?.netShort), "mono")}
        ${row("Retail Net Calls", fmt(ps.client_ce_net_buy ?? p.client?.options?.ce?.netBuy), "mono")}
        <div class="section-label dii">DII (Domestic)</div>
        ${row("DII Call Shift", fmt(ps.dii_ce_net_short_change ?? dii.options?.ce?.netShort), "mono")}
        ${row("DII Put Shift", fmt(ps.dii_pe_net_short_change ?? dii.options?.pe?.netShort), "mono")}
        ${row("DII Futures Net", fmt(ps.dii_fut_net_change ?? dii.futures?.net), "mono")}
      </div></div>`;
  }

  function rollsPanel(mf) {
    const rolls = mf.rolls || mf.index_rolls || {};
    if (!Object.keys(rolls).length) return `<div class="error-card">No index roll data.</div>`;
    return `<div class="instrument-block"><div class="block-header">Index Rolls, Magnet Strike & Expiry Targets</div>
      <div class="rolls-grid">${Object.entries(rolls).map(([sym, r]) => `
        <div class="roll-card ${r.resistance_roll_type === "BULLISH" ? "bullish" : r.resistance_roll_type === "BEARISH" ? "bearish" : ""}">
          <div class="roll-head"><span class="roll-symbol">${sym}</span>
          <span class="roll-meta">LTP ${NFOD.utils.formatIndianNum(r.ltp)} · Max Pain ${NFOD.utils.formatIndianNum(r.max_pain)} · PCR ${r.pcr_oi ? r.pcr_oi.toFixed(2) : "--"}</span></div>
          <div class="magnet"><span>🧲 Magnet ${NFOD.utils.formatIndianNum(r.magnet_strike)}</span>
          <span>🎯 ${r.expiry_range || "--"}</span></div>
          <div class="roll-cells">
            <div><span class="roll-label">RESISTANCE</span>
              <span class="${r.resistance_roll_type === "BULLISH" ? "pos-up" : r.resistance_roll_type === "BEARISH" ? "pos-down" : ""}">${r.resistance_roll}</span>
              <div class="roll-desc">${r.resistance_roll_desc}</div></div>
            <div><span class="roll-label">SUPPORT</span>
              <span class="${r.support_roll_type === "BULLISH" ? "pos-up" : r.support_roll_type === "BEARISH" ? "pos-down" : ""}">${r.support_roll}</span>
              <div class="roll-desc">${r.support_roll_desc}</div></div>
          </div>
          ${(r.traps_and_squeezes || []).map(t => `<div class="trap">${t.badge}: ${t.desc}</div>`).join("")}
        </div>`).join("")}
      </div></div>`;
  }

  function convictionPanel(mf) {
    const conv = mf.conviction || mf.conviction_trends || {};
    let current = "NIFTY";
    const renderTable = (sym) => {
      const c = conv[sym];
      if (!c || !c.strikes || !c.strikes.length) return `<tr><td colspan="7" class="muted">No history yet.</td></tr>`;
      return c.strikes.map(s => `
        <tr><td>${s.ce_flow_attr || "--"}</td><td>${s.ce_conviction || "--"}</td>
        <td class="${s.ce_trend_delta > 0 ? "pos-down" : "pos-up"}">${s.ce_trend_delta > 0 ? "+" : ""}${NFOD.utils.formatIndianNum(s.ce_trend_delta)}</td>
        <td class="strike">${s.strike.toLocaleString("en-IN")}</td>
        <td class="${s.pe_trend_delta > 0 ? "pos-up" : "pos-down"}">${s.pe_trend_delta > 0 ? "+" : ""}${NFOD.utils.formatIndianNum(s.pe_trend_delta)}</td>
        <td>${s.pe_conviction || "--"}</td><td>${s.pe_flow_attr || "--"}</td></tr>`).join("");
    };
    return `<div class="instrument-block"><div class="block-header">Multi-Day Strike Conviction Matrix</div>
      <div class="conv-tabs">${Object.keys(conv).map(sym =>
        `<button class="tab-btn ${sym === current ? "active" : ""}" data-sym="${sym}">${sym}</button>`).join("")}</div>
      <table class="data-table"><thead><tr>
        <th>CE Flow</th><th>CE Conviction</th><th>Call OI Δ</th><th>Strike</th>
        <th>Put OI Δ</th><th>PE Conviction</th><th>PE Flow</th></tr></thead>
      <tbody id="conv-body">${renderTable(current)}</tbody></table></div>`;
  }

  function breadthPanel(mf) {
    const b = mf.breadth || mf.stock_breadth || {};
    const cols = [
      { key: "call_writing_bearish", title: "Fresh Call Write (Capping Upside)", cls: "down" },
      { key: "put_writing_bullish", title: "Fresh Put Write (Defending Floor)", cls: "up" },
      { key: "call_unwinding_bullish", title: "Call Unwind (Short Squeeze)", cls: "up" },
      { key: "put_unwinding_bearish", title: "Put Unwind (Floor Breakdown)", cls: "down" },
    ];
    return `<div class="instrument-block"><div class="block-header">Market Breadth — Top Stock Options Activity</div>
      <div class="breadth-grid">${cols.map(c => `
        <div class="breadth-col"><div class="breadth-head ${c.cls}">${c.title}</div>
        <table class="data-table compact">${(b[c.key] || []).slice(0, 10).map(x => `
          <tr><td class="mono">${x.symbol}</td><td>${x.ltp || "--"}</td>
          <td>${x.top_ce_write_strike ?? x.top_pe_write_strike ?? "--"}</td>
          <td class="${c.cls}">${NFOD.utils.formatIndianNum(x.net_ce_doi ?? x.net_pe_doi)}</td></tr>`).join("")}
        </table></div>`).join("")}</div></div>`;
  }

  function divergencePanel(mf) {
    const div = mf.divergence || mf.flow_divergence || [];
    if (!div.length) return "";
    return `<div class="instrument-block"><div class="block-header">Flow Divergence — Strike-Level Conflicts</div>
      <div class="divg-list">${div.map(d => `
        <div class="divg-item"><span class="divg-sym">${d.symbol}</span>
        <span class="divg-strike">${d.strike}</span><span class="badge warn">${d.type}</span>
        <span class="divg-desc">${d.desc}</span></div>`).join("")}</div></div>`;
  }

  async function render(state) {
    const view = document.getElementById("view-verdict");
    if (!cached) cached = await NFOD.data.loadMoneyFlow();
    if (!cached) {
      view.innerHTML = `<div class="error-card">Money Flow verdict data not found.
        <button class="btn btn-sm retry-btn" onclick="NFOD.views.verdict.reset()">Retry</button></div>`;
      return;
    }
    view.innerHTML = execBanner(cached) + rollsPanel(cached) + stancePanel(cached) +
      convictionPanel(cached) + divergencePanel(cached) + breadthPanel(cached);
    view.querySelectorAll(".conv-tabs .tab-btn").forEach(btn => {
      btn.onclick = () => {
        view.querySelectorAll(".conv-tabs .tab-btn").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        const c = (cached.conviction || cached.conviction_trends || {})[btn.dataset.sym];
        view.querySelector("#conv-body").innerHTML = (c && c.strikes || []).map(s => `
          <tr><td>${s.ce_flow_attr || "--"}</td><td>${s.ce_conviction || "--"}</td>
          <td class="${s.ce_trend_delta > 0 ? "pos-down" : "pos-up"}">${s.ce_trend_delta > 0 ? "+" : ""}${NFOD.utils.formatIndianNum(s.ce_trend_delta)}</td>
          <td class="strike">${s.strike.toLocaleString("en-IN")}</td>
          <td class="${s.pe_trend_delta > 0 ? "pos-up" : "pos-down"}">${s.pe_trend_delta > 0 ? "+" : ""}${NFOD.utils.formatIndianNum(s.pe_trend_delta)}</td>
          <td>${s.pe_conviction || "--"}</td><td>${s.pe_flow_attr || "--"}</td></tr>`).join("");
      };
    });
  }
  return { render, reset: () => { cached = null; } };
})();
```

- [ ] **Step 2: Verify**

Switch to Verdict view: executive banner with bias badge + score gauge, rolls cards per index (magnet/max-pain/PCR), stance rows (FII/Pro/Retail/DII), conviction matrix with NIFTY/BANKNIFTY tab switching, flow divergence items, 4-column breadth. Missing money_flow_data.json → error card + Retry works (test by temporarily renaming the JSON).

- [ ] **Step 3: Commit**

```bash
git add views/verdict.js
git commit -m "feat(verdict): money-flow verdict view on nested schema"
```

---

