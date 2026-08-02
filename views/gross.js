window.NFOD = window.NFOD || {};
NFOD.views = NFOD.views || {};
NFOD.views.gross = (function () {
  const INSTRUMENTS = [
    { id: "index-futures", title: "Index Futures", l: "Future Index Long", s: "Future Index Short" },
    { id: "index-calls", title: "Index Calls", l: "Option Index Call Long", s: "Option Index Call Short" },
    { id: "index-puts", title: "Index Puts", l: "Option Index Put Long", s: "Option Index Put Short" },
    { id: "stock-futures", title: "Stock Futures", l: "Future Stock Long", s: "Future Stock Short" },
    { id: "stock-calls", title: "Stock Calls", l: "Option Stock Call Long", s: "Option Stock Call Short" },
    { id: "stock-puts", title: "Stock Puts", l: "Option Stock Put Long", s: "Option Stock Put Short" },
  ];
  const PARTS = ["Client", "DII", "FII", "Pro"];
  const PARTICIPANT_LABELS = { Client: "Client", DII: "DII", FII: "FII", Pro: "Pro" };
  const DAYS = 8; // sparkline window
  let renderSeq = 0;

  function sparklineFor(part, inst, dateIdx) {
    const vals = [];
    const start = Math.max(0, dateIdx - DAYS + 1);
    for (let i = start; i <= dateIdx; i++) {
      const d = NFOD.state.dates[i];
      const m = NFOD.data.getParticipantMap(d);
      const r = m[part];
      if (!r) { vals.push(null); continue; }
      vals.push((r[inst.l] || 0) - (r[inst.s] || 0));
    }
    const clean = vals.filter(v => v !== null);
    if (!clean.length) return "";
    const last = clean[clean.length - 1];
    const color = last >= 0 ? "var(--up)" : "var(--down)";
    const cell = document.createElement("td");
    cell.className = "spark-cell";
    NFOD.sparkline.render(cell, clean, color);
    return cell.outerHTML;
  }

  function renderInstrumentTable(inst, dateIdx) {
    const dates = NFOD.state.dates;
    const today = dates[dateIdx], prev = dates[dateIdx - 1], prev2 = dates[dateIdx - 2];
    const tm = NFOD.data.getParticipantMap(today);
    const pm = prev ? NFOD.data.getParticipantMap(prev) : null;
    const p2m = prev2 ? NFOD.data.getParticipantMap(prev2) : null;
    let rows = "";
    PARTS.forEach(p => {
      const r = tm[p] || {}, rp = pm && pm[p], rp2 = p2m && p2m[p];
      const chg = (col) => rp ? (r[col] || 0) - (rp[col] || 0) : null;
      const longD = chg(inst.l), shortD = chg(inst.s);
      const net = (longD !== null && shortD !== null) ? longD - shortD : null;
      const carried = r[inst.l] - r[inst.s];
      const carried1 = rp ? rp[inst.l] - rp[inst.s] : null;
      const carried2 = rp2 ? rp2[inst.l] - rp2[inst.s] : null;
      const cls = v => v === null ? "-" : v >= 0 ? "pos-up" : "pos-down";
      // Action labels (Added/Closed/Bought/Sold) like the old dashboard
      const act = (v, bearishPos) => v === null || v === 0 ? ["-", ""]
        : v > 0 ? ["Added", bearishPos ? "pos-down" : "pos-up"]
        : ["Closed", bearishPos ? "pos-up" : "pos-down"];
      const actNet = v => v === null || v === 0 ? ["-", ""] : v > 0 ? ["Bought", "pos-up"] : ["Sold", "pos-down"];
      const [la, lc] = act(longD, false);
      const [sa, sc] = act(shortD, true);
      const [na, nc] = actNet(net);
      rows += `<tr>
        <td class="sticky-col-first participant">${PARTICIPANT_LABELS[p] || p}</td>
        <td class="action-label ${lc}">${la}</td><td class="${lc}">${NFOD.utils.formatIndianNum(longD)}</td>
        <td class="action-label ${sc}">${sa}</td><td class="${sc}">${NFOD.utils.formatIndianNum(shortD)}</td>
        <td class="action-label ${nc}">${na}</td><td class="${nc}">${NFOD.utils.formatIndianNum(net)}</td>
        <td class="${cls(carried)}">${NFOD.utils.formatIndianNum(carried)}</td>
        <td class="${cls(carried1)}">${NFOD.utils.formatIndianNum(carried1)}</td>
        <td class="${cls(carried2)}">${NFOD.utils.formatIndianNum(carried2)}</td>
        ${sparklineFor(p, inst, dateIdx)}</tr>`;
    });
    return `<div class="instrument-block">
      <div class="block-header">${inst.title}</div>
      <div class="table-scroll">
        <table class="data-table oi-table">
          <colgroup>
            <col class="col-participant">
            <col class="col-label"><col class="col-value">
            <col class="col-label"><col class="col-value">
            <col class="col-label"><col class="col-value">
            <col class="col-value"><col class="col-value"><col class="col-value">
            <col class="col-spark">
          </colgroup>
          <thead><tr>
            <th class="sticky-col-first">Participant</th>
            <th colspan="2">Longs</th><th colspan="2">Shorts</th><th colspan="2">Net Today</th>
            <th>Today</th><th>1D Ago</th><th>2D Ago</th><th>Trend</th>
          </tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    </div>`;
  }

  function renderKPIs(tm, pm) {
    const fii = tm["FII"], fiiP = pm && pm["FII"];
    const fiiFut = fii && fiiP ? (fii["Future Index Long"] - fiiP["Future Index Long"]) - (fii["Future Index Short"] - fiiP["Future Index Short"]) : null;
    const client = tm["Client"], clP = pm && pm["Client"];
    const clCalls = client && clP ? (client["Option Index Call Long"] - clP["Option Index Call Long"]) - (client["Option Index Call Short"] - clP["Option Index Call Short"]) : null;
    const pro = tm["Pro"], proP = pm && pm["Pro"];
    const prCalls = pro && proP ? (pro["Option Index Call Long"] - proP["Option Index Call Long"]) - (pro["Option Index Call Short"] - proP["Option Index Call Short"]) : null;
    const prPuts = pro && proP ? (pro["Option Index Put Short"] - proP["Option Index Put Short"]) - (pro["Option Index Put Long"] - proP["Option Index Put Long"]) : null;
    const bias = (fiiFut || 0) + (prCalls || 0) + (prPuts || 0);
    const biasTxt = bias > 20000 ? "BULLISH" : bias < -20000 ? "BEARISH" : "NEUTRAL / MIXED";
    const cls = v => v === null ? "-" : v >= 0 ? "pos-up" : "pos-down";
    return `<section class="kpi-bar">
      ${kpi("FII Index Futures (Net)", NFOD.utils.formatIndianNum(fiiFut), cls(fiiFut))}
      ${kpi("Client Index Calls (Net)", NFOD.utils.formatIndianNum(clCalls), cls(clCalls))}
      ${kpi("Pro Index Calls (Net)", NFOD.utils.formatIndianNum(prCalls), cls(prCalls))}
      <div class="kpi-card">
        <div class="kpi-header">Institutional Bias</div>
        <div class="kpi-value ${bias > 0 ? "pos-up" : bias < 0 ? "pos-down" : ""}">${biasTxt}</div>
        <div class="kpi-sub">Score ${bias > 0 ? "+" : ""}${bias}</div>
      </div>
    </section>`;
  }
  function kpi(h, v, c) {
    return `<div class="kpi-card"><div class="kpi-header">${h}</div>
      <div class="kpi-value ${c}">${v}</div></div>`;
  }

  function renderTakeaways(moneyFlow) {
    const ps = (moneyFlow && moneyFlow.participant_summary) || {};
    if (!Object.keys(ps).length) return "";
    const score = ps.smart_money_score || 0;
    const icon = score >= 15 ? "🟢" : score <= -15 ? "🔴" : "🟡";
    const verdict = score >= 40 ? "Strongly Bullish" : score >= 15 ? "Bullish"
      : score <= -40 ? "Strongly Bearish" : score <= -15 ? "Bearish" : "Mixed / Neutral";
    const lines = [];
    lines.push(`${icon} <strong>${verdict}</strong> — Smart Money Score: <strong>${score > 0 ? "+" : ""}${score}</strong>`);
    const d = ps.date || "";
    const r = NFOD.utils.daysToMonthlyExpiry(d);
    if (d) lines.push("📅 Trading Session: " + d + (NFOD.utils.monthlyExpirySuffix(r) || ""));
    const fiiActs = [];
    const a = v => NFOD.utils.formatIndianNum(Math.abs(v));
    if (ps.fii_fut_net_change > 5000) fiiActs.push("bought " + a(ps.fii_fut_net_change) + " Index Futures");
    else if (ps.fii_fut_net_change < -5000) fiiActs.push("sold " + a(ps.fii_fut_net_change) + " Index Futures");
    if (ps.fii_ce_long_change > 20000) fiiActs.push("bought " + a(ps.fii_ce_long_change) + " Calls");
    if (ps.fii_ce_short_change > 20000) fiiActs.push("wrote " + a(ps.fii_ce_short_change) + " Calls");
    if (ps.fii_pe_short_change > 20000) fiiActs.push("wrote " + a(ps.fii_pe_short_change) + " Puts");
    if (fiiActs.length) lines.push("🏛 <strong>FII:</strong> " + fiiActs.join("; ") + ".");
    if (ps.retail_trap_alarm) lines.push("🔴 " + ps.retail_trap_alarm);
    else if (ps.retail_confirmation_message) lines.push("🟢 " + ps.retail_confirmation_message);
    return `<div class="takeaways"><div class="takeaways-title">Key Takeaways</div>
      ${lines.map(l => `<div class="takeaway-item">${l}</div>`).join("")}</div>`;
  }

  function renderRightRail(netActions) {
    return `<div class="right-rail">
      <div class="rail-title">Today's Action</div>
      ${PARTS.map(p => {
        const acts = netActions.filter(x => x.participant === p);
        return `<div class="instrument-block rail-card">
          <div class="block-header">${PARTICIPANT_LABELS[p] || p}</div>
          <table class="data-table compact rail-table">
            <colgroup>
              <col class="col-inst"><col class="col-act"><col class="col-val">
            </colgroup>
            ${acts.map(x => `
            <tr><th scope="row" class="action-label">${x.instrument}</th>
            <td class="${x.net >= 0 ? "pos-up" : "pos-down"}">${x.action}</td>
            <td class="${x.net >= 0 ? "pos-up" : "pos-down"}">${NFOD.utils.formatIndianNum(x.net)}</td></tr>`).join("")}
          </table></div>`;
      }).join("")}
    </div>`;
  }

  function render(state) {
    const view = document.getElementById("view-gross");
    const token = ++renderSeq;
    const idx = state.dateIndex;
    const tm = NFOD.data.getParticipantMap(state.dates[idx]);
    const pm = state.dates[idx - 1] ? NFOD.data.getParticipantMap(state.dates[idx - 1]) : null;
    let netActions = [];
    INSTRUMENTS.forEach(inst => {
      PARTS.forEach(p => {
        const r = tm[p] || {}, rp = pm && pm[p];
        const net = rp ? (r[inst.l] - rp[inst.l]) - (r[inst.s] - rp[inst.s]) : null;
        if (net) netActions.push({ participant: p, instrument: inst.title, action: net > 0 ? "Bought" : "Sold", net });
      });
    });
    const body = renderKPIs(tm, pm) +
      `<main class="dash-grid">
        <div class="main-col">${INSTRUMENTS.map(i => renderInstrumentTable(i, idx)).join("")}</div>
        ${renderRightRail(netActions)}
      </main>`;
    // Reserve the takeaways slot (min-height in CSS) so the async fill below
    // doesn't shift the page — that append was the dominant CLS source.
    view.innerHTML = body + `<div class="takeaways" id="takeaways-slot"></div>`;
    NFOD.data.loadMoneyFlow().then(mf => {
      if (token !== renderSeq) return;      // stale render — a newer one superseded us
      const slot = view.querySelector("#takeaways-slot");
      if (slot) slot.innerHTML = renderTakeaways(mf);
    });
  }
  return { render };
})();
