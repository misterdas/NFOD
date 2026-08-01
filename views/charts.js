window.NFOD = window.NFOD || {};
NFOD.views = NFOD.views || {};
NFOD.views.charts = (function () {
  let ohlc = null, instances = [];
  async function ensureApex() {
    if (window.ApexCharts) return;
    await new Promise((res, rej) => {
      const s = document.createElement("script");
      s.src = "https://cdn.jsdelivr.net/npm/apexcharts";
      s.onload = res; s.onerror = rej;
      document.body.appendChild(s);
    });
  }
  function chartTheme() { return document.body.classList.contains("theme-light") ? "light" : "dark"; }
  function buildSeries() {
    const dates = NFOD.state.dates.slice(1);          // need prev-day for change
    const parts = { FII: { c: [], p: [] }, DII: { c: [], p: [] }, Pro: { c: [], p: [] }, Client: { c: [], p: [] } };
    dates.forEach(d => {
      const m = NFOD.data.getParticipantMap(d);
      ["FII", "DII", "Pro", "Client"].forEach(k => {
        const r = m[k] || {};
        parts[k].c.push((r["Option Index Call Long"] || 0) - (r["Option Index Call Short"] || 0));
        parts[k].p.push((r["Option Index Put Long"] || 0) - (r["Option Index Put Short"] || 0));
      });
    });
    return { dates, parts };
  }
  function candleData() {
    if (!ohlc || !ohlc.nifty) return [];
    const map = {};
    ohlc.nifty.forEach(r => {
      const [y, m, d] = r.date.split("-");             // OHLC is YYYY-MM-DD; state.dates are DD-MM-YYYY
      map[`${d}-${m}-${y}`] = [r.open, r.high, r.low, r.close];
    });
    return NFOD.state.dates.slice(1).map((d, i) => {
      const o = map[d];
      const x = i * 864e5;
      return o ? { x, y: o } : null;
    }).filter(Boolean);
  }
  function renderChart(el, label, callColor, putColor) {
    const { dates, parts } = buildSeries();
    const candles = candleData();
    const base = { chart: { type: "candlestick", height: 360, toolbar: { show: false }, background: "transparent" },
      theme: { mode: chartTheme() } };
    const cfg = candles.length
      ? { ...base, series: [
          { name: "NIFTY", data: candles },
          { name: label + " Calls", type: "line", data: parts[label].c },
          { name: label + " Puts", type: "line", data: parts[label].p } ],
          xaxis: { type: "datetime", labels: { show: false } },
          colors: ["#38bdf8", callColor, putColor],
          stroke: { width: [1, 2, 2] },
          yaxis: [{ labels: { formatter: v => v.toLocaleString("en-IN") }, title: { text: "NIFTY" } },
                  { opposite: true, labels: { formatter: v => (v / 1e3).toFixed(0) + "K" } }] }
      : { ...base, chart: { ...base.chart, type: "line" },
          series: [{ name: label + " Calls", data: parts[label].c }, { name: label + " Puts", data: parts[label].p }],
          xaxis: { categories: dates, labels: { rotate: -45 } },
          colors: [callColor, putColor], stroke: { width: 2 } };
    try {
      const a = new ApexCharts(el, cfg);
      a.render();
      instances.push(a);
    } catch (e) {
      el.innerHTML = `<div class="error-card">Chart failed to render.</div>`;
    }
  }
  async function render(state) {
    const view = document.getElementById("view-charts");
    try {
      await ensureApex();
    } catch (e) {
      view.innerHTML = `<div class="error-card">ApexCharts CDN unavailable — charts disabled.</div>`;
      return;
    }
    if (!ohlc) ohlc = await NFOD.data.loadOHLC();
    instances.forEach(i => i && i.destroy());
    instances = [];
    view.innerHTML = `<div class="charts-toolbar">
        <span class="toolbar-label">Range</span>
        <button class="btn btn-sm" data-range="20">1M</button>
        <button class="btn btn-sm" data-range="60">3M</button>
        <button class="btn btn-sm" data-range="0">All</button>
      </div>
      <div class="charts-grid">
        <div class="chart-card" id="ch-fii"></div><div class="chart-card" id="ch-dii"></div>
        <div class="chart-card" id="ch-pro"></div><div class="chart-card" id="ch-client"></div>
      </div>`;
    renderChart(document.getElementById("ch-fii"), "FII", "#ef4444", "#34d399");
    renderChart(document.getElementById("ch-dii"), "DII", "#ef4444", "#34d399");
    renderChart(document.getElementById("ch-pro"), "Pro", "#ef4444", "#34d399");
    renderChart(document.getElementById("ch-client"), "Client", "#ef4444", "#34d399");
    // range selector — simplistic: re-render with truncated dates (Task 10 keeps All; note ceiling)
    view.querySelectorAll("[data-range]").forEach(btn => {
      btn.onclick = () => { /* ponytail: range filtering of series data not yet wired — add when needed */ };
    });
  }
  return { render };
})();
