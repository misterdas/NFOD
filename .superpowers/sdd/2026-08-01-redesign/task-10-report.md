# Task 10 Report: views/charts.js — ApexCharts candlestick + lines

## Status: DONE

## What was implemented

Created `views/charts.js` — `NFOD.views.charts.render(state)` rendering 4 ApexCharts (FII/DII/Pro/Client) with NIFTY OHLC candlestick overlay + call/put net-short lines, per the task brief. Brief code copied verbatim except two fixes (below).

Interfaces used: `NFOD.state.dates` (DD-MM-YYYY), `NFOD.data.getParticipantMap(d)` (DD-MM-YYYY), `NFOD.data.loadOHLC()` (YYYY-MM-DD), `document.body.classList` theme check. Not touched: `app.js`, `index.html`, `data.js`, `styles.css`.

## Bugs found + fixed in the brief's code

### Bug 1 — candleData() date-key mismatch (would render NO candles)
Brief's `candleData()` built `map` keyed by `r.date` (OHLC = `YYYY-MM-DD`) but looked up `map[d]` where `d` comes from `NFOD.state.dates.slice(1)` (DD-MM-YYYY). Every lookup missed → `candleData()` returned `[]` → every chart fell back to line-only. Fix: convert OHLC date to DD-MM-YYYY when building the map:

```js
ohlc.nifty.forEach(r => {
  const [y, m, d] = r.date.split("-");             // OHLC is YYYY-MM-DD; state.dates are DD-MM-YYYY
  map[`${d}-${m}-${y}`] = [r.open, r.high, r.low, r.close];
});
```

Verified: all 4 charts now get `chart.type: "candlestick"` with 42 candle points matched across all 42 participant dates (line_points all 42 too).

### Bug 2 — CDN-failure fallback never triggered (per-card errors instead)
Brief's `render()` did `await ensureApex().catch(() => { view.innerHTML = error-card; return; })` — but `return` inside the arrow only returns from the arrow, execution continued to `view.innerHTML = toolbar+grid` (clobbering the error-card) then `renderChart` → `new ApexCharts(...)` threw → 4× "Chart failed to render." Fix: wrap in try/catch with an early `return`:

```js
try {
  await ensureApex();
} catch (e) {
  view.innerHTML = `<div class="error-card">ApexCharts CDN unavailable — charts disabled.</div>`;
  return;
}
```

Verified: with CDN route-blocked, `#view-charts` shows exactly one error-card "ApexCharts CDN unavailable — charts disabled.", zero console errors.

## Verification (headless Chrome + Playwright, over HTTP server)

Ran against real `index.html` + real `docs/ohlc_data.json` served from `python -m http.server 8734` (file:// blocked fetch by CORS). Test scripts in `/tmp/task10_verify*.py` (ephemeral).

Commands:
- `python -m http.server 8734 --bind 127.0.0.1 &`
- `python /tmp/task10_verify4.py` (happy path via `ApexCharts` Proxy constructor capture)
- `python /tmp/task10_verify5.py` (SVG content + light-theme re-render)
- `python /tmp/task10_verify6.py` (CDN-blocked + OHLC-blocked fallbacks)
- `python /tmp/task10_verify7.py` (CDN-blocked after Bug-2 fix)

### Happy path (real OHLC)
- 4 chart cards render, `chart.type: "candlestick"`, 3 series each: NIFTY (42 candles), `<Label> Calls` (42 pts), `<Label> Puts` (42 pts).
- SVG aria-label: "candlestick chart with 3 data series: NIFTY, FII Calls, FII Puts".
- Zero console errors, zero page errors.
- ApexCharts v4 renders to canvas; the wrapper `<svg class="apexcharts-svg">` is a mask container — candle presence proven via captured configs (42 candle points) rather than raw DOM.

### Theme
`chartTheme()` re-reads `document.body.classList` on every `render()` call → charts render with `theme: "dark"` at load and `theme: "light"` after manual `render()` under `body.theme-light`. Verified: re-render returns `["light","light","light","light"]`. NOTE: current `app.js` `bindTheme()` does NOT re-invoke `renderActiveView()`, so toggling the button alone won't refresh charts until Task 12 wires `render` into the theme handler — charts.js is correctly structured for it (per-bell-brief note). Not changed here.

### Fallbacks
- CDN blocked → single error-card message, no throw. (after Bug-2 fix)
- OHLC fetch blocked (`ohlc = null`) → 4 charts render as `chart.type: "line"` with 2 series (Calls/Puts only). Verified.

## Files changed

- `views/charts.js` (created; brief code + 2 fixes above)
- `.superpowers/sdd/2026-08-01-redesign/task-10-report.md` (this file)

## Self-review

- Date-key fix is minimal and matches the old dashboard's `DD-MM-YYYY`→`YYYY-MM-YYYY` convention (converted OHLC key to lookup format, per task's suggested option).
- CDN catch early-return preserves intended single-message fallback.
- Range selector buttons remain stub `onclick` (no-op) — per spec Non-Goals, kept verbatim.
- `ohlc` cached in closure across renders; `instances` destroyed before re-render → no chart leaks on view switching/theme re-render.
- No changes to other files; commit is `views/charts.js` only.

## Concerns

- Range buttons (1M/3M/All) are decorative no-ops until range filtering is wired (documented ponytail, per spec).
- Theme toggle needs Task 12 wiring in `app.js` to re-render charts (charts.js side ready).
- Minor: `render()` resolves after `renderChart` calls but ApexCharts `.render()` is async and un-awaited; harmless since instances are tracked.
