window.NFOD = window.NFOD || {};
NFOD.views = NFOD.views || {};
NFOD.views.charts = (function () {
  let ohlc = null, instances = [];
  const CHART_BASE = new Date("2020-01-01T00:00:00Z").getTime();   // origin for uniform 1-day index spacing
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
    const dates = NFOD.state.dates.slice(1);          // skip first date (no prev-day context)
    const parts = { FII: { c: [], p: [] }, DII: { c: [], p: [] }, Pro: { c: [], p: [] }, Client: { c: [], p: [] } };
    dates.forEach((d, i) => {
      const x = CHART_BASE + i * 864e5;               // uniform spacing — no weekend/holiday gaps
      const m = NFOD.data.getParticipantMap(d);
      ["FII", "DII", "Pro", "Client"].forEach(k => {
        const r = m[k] || {};
        const callNet = (r["Option Index Call Long"] || 0) - (r["Option Index Call Short"] || 0);
        const putNet = (r["Option Index Put Long"] || 0) - (r["Option Index Put Short"] || 0);
        parts[k].c.push({ x, y: callNet });
        parts[k].p.push({ x, y: putNet });
      });
    });
    return { dates, parts };
  }
  function candleData() {
    if (!ohlc || !ohlc.nifty) return [];
    const map = {};
    ohlc.nifty.forEach(r => {
      if (!r.date) return;
      const parts = r.date.split("-");
      if (parts.length !== 3) return;
      const [y, m, d] = parts;
      const formattedDate = `${d.padStart(2, "0")}-${m.padStart(2, "0")}-${y}`;
      map[formattedDate] = [r.open, r.high, r.low, r.close];
    });
    const out = [];
    NFOD.state.dates.slice(1).forEach((d, i) => {
      const o = map[d];
      if (o) out.push({ x: CHART_BASE + i * 864e5, y: o });   // x from ORIGINAL index — stays aligned when filtered
    });
    return out;
  }
  function renderChart(el, label, callColor, putColor) {
    const { dates, parts } = buildSeries();
    const candles = candleData();
    const base = { chart: { type: "candlestick", height: 360, toolbar: { show: false }, background: "transparent", zoom: { enabled: false } },
      theme: { mode: chartTheme() }, legend: { show: false } };
    const xaxis = { type: "datetime", labels: { show: false } };
    const tooltip = {
      x: { formatter: (val) => { const i = Math.round((val - CHART_BASE) / 864e5); return dates[i] || ""; } },
      custom: candles.length ? ({ seriesIndex, dataPointIndex, w }) => {
        const s = w.config.series[seriesIndex];
        const xv = w.globals.seriesX[seriesIndex][dataPointIndex];
        const date = dates[Math.round((xv - CHART_BASE) / 864e5)] || "";
        if (s.type && s.type !== "candlestick") {
          return `<div class="apexcharts-custom-tooltip"><div class="tooltip-date">${date}</div>${s.name}: <strong>${w.seriesData.series[seriesIndex][dataPointIndex]}</strong></div>`;
        }
        const o = w.candleData.seriesCandleO[seriesIndex][dataPointIndex];
        const h = w.candleData.seriesCandleH[seriesIndex][dataPointIndex];
        const l = w.candleData.seriesCandleL[seriesIndex][dataPointIndex];
        const c = w.candleData.seriesCandleC[seriesIndex][dataPointIndex];
        return `<div class="apexcharts-tooltip-box apexcharts-tooltip-candlestick"><div class="tooltip-date">${date}</div>` +
          `<div>Open: <span class="value">${o}</span></div>` +
          `<div>High: <span class="value">${h}</span></div>` +
          `<div>Low: <span class="value">${l}</span></div>` +
          `<div>Close: <span class="value">${c}</span></div></div>`;
      } : undefined,
    };
    const cfg = candles.length
      ? { ...base, series: [
          { name: "NIFTY", data: candles },
          { name: label + " Calls", type: "line", data: parts[label].c },
          { name: label + " Puts", type: "line", data: parts[label].p } ],
          xaxis, tooltip,
          colors: ["#38bdf8", callColor, putColor],
          stroke: { width: [1, 2, 2] },
          yaxis: [{ labels: { show: false } },
                  { opposite: true, labels: { show: false } }] }
      : { ...base, chart: { ...base.chart, type: "line" },
          series: [{ name: label + " Calls", data: parts[label].c }, { name: label + " Puts", data: parts[label].p }],
          xaxis, tooltip,
          colors: [callColor, putColor], stroke: { width: 2 },
          yaxis: [{ labels: { show: false } },
                  { opposite: true, labels: { show: false } }] }
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
    } catch {
      view.innerHTML = `<div class="error-card">ApexCharts CDN unavailable — charts disabled.</div>`;
      return;
    }
    if (!ohlc) ohlc = await NFOD.data.loadOHLC();
    instances.forEach(i => i && i.destroy());
    instances = [];
    view.innerHTML = `<div class="charts-grid">
        <div class="chart-card"><h3 class="chart-title">FII</h3><div id="ch-fii"></div></div>
        <div class="chart-card"><h3 class="chart-title">DII</h3><div id="ch-dii"></div></div>
        <div class="chart-card"><h3 class="chart-title">Pros</h3><div id="ch-pro"></div></div>
        <div class="chart-card"><h3 class="chart-title">Clients</h3><div id="ch-client"></div></div>
      </div>`;
    renderChart(document.getElementById("ch-fii"), "FII", "#ef4444", "#34d399");
    renderChart(document.getElementById("ch-dii"), "DII", "#ef4444", "#34d399");
    renderChart(document.getElementById("ch-pro"), "Pro", "#ef4444", "#34d399");
    renderChart(document.getElementById("ch-client"), "Client", "#ef4444", "#34d399");
  }
  return { render };
})();
