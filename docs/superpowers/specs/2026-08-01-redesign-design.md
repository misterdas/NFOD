# NFOD Dashboard — Full Overhaul Design

**Date**: 2026-08-01
**Branch**: `redesign/overhaul`
**Status**: Approved (sections 1–5 reviewed)

## 1. Goals

Turn the existing F&O OI dashboard into a high-quality modern fintech website (Linear/Stripe-grade). Full visual + UX overhaul with new features, on a new modular architecture. Data pipeline stays NSE-sourced and GitHub-Pages-deployed.

## 2. Visual Direction

- **Style**: Modern fintech SaaS (Linear/Stripe aesthetic).
- **Theme**: Dark default + light toggle, driven by one token set.
- **Typography**: Inter (UI/body) + JetBrains Mono (all numbers/strikes/tables). Tabular numerals. Scale 11px→32px.
- **Colors** (CSS custom properties): surface 1/2/3, border, text 1/2/3, semantic up/down/warn/info, accent gradient.
- **Spacing**: 4px base grid. **Radius**: 6/8/12/16. **Shadows**: 3 levels, theme-tinted.
- **Motion**: 150/250/400ms ease-out; fade-up, number count-up, hover lift; `prefers-reduced-motion` respected.
- **Status color semantics**: Δ up=green, down=red, neutral=text-3. Green ≠ "good" — direction only; bias labels carry semantics.
- **Component kit** (token-driven): KPI card, data table, stat row, badge/pill, tag, tooltip, button, select, toggle, skeleton, date-chip, sparkline.
- **Loading/error**: skeleton on first paint, inline error card + Retry, empty-state messages.

## 3. Information Architecture & Layout

### Header (sticky)
- Brand mark + "OI Analysis" wordmark + subtitle.
- Date navigation (‹ / calendar / › + Latest chip), market status pill (● LIVE / ○ CLOSED / PRE-MARKET + NIFTY spot), theme toggle, menu. Compact on mobile.

### View switcher (tab bar)
- **Gross OI** · **Verdict** · **Charts**. Active pill + underline, keyboard accessible.

### View 1 — Gross OI
- 4 KPI cards (FII Index Futures Net, Client Index Calls Net, Pro Index Calls Net, Institutional Bias with score meter).
- Grid: 6 instrument tables (main) + right rail ("Today's Action" per participant + Key Takeaways).
- Tables: sticky header, grouped columns (Longs/Shorts/Net Today/Carried 3-day), inline sparklines, total row.

### View 2 — Verdict
- Executive banner + Smart Money Score gauge.
- Index Rolls & Magnet Strikes (per-index cards).
- FII/Pro/DII stance panel.
- Multi-Day Conviction Matrix (NIFTY/BANKNIFTY tabs).
- Flow Divergence table.
- 4-column Market Breadth grid.

### View 3 — Charts
- 4 candlestick+line charts (FII/DII/Pro/Client) + NIFTY overlay.
- Toolbar: range selector (1M/3M/All), legend toggles, download PNG.

### Footer
- "Gopal Das · NFD Participant OI Engine v3.0" + disclaimer.

### Responsive
- ≤1200px: right rail drops below main. ≤900px: tabs scroll, KPI 2×2. ≤640px: KPI 2×2 compact, tables horizontal-scroll, charts stacked.

## 4. Data Layer & Schema Reshape

### File contract change (fetcher.py)
- `_EMBEDDED_CSV` moves from `app.js` → `data.js`.
- `update_embedded_csv()` boundary strings: `var _EMBEDDED_CSV="` … `";` in `data.js`.
- CSV format unchanged. All other fetcher logic identical.

### data.js responsibilities
- Expose `_EMBEDDED_CSV` + `loadFDCP()` (parse to rows).
- `loadMoneyFlow()`, `loadOHLC()` — fetch with day-bucket cache-bust (`?d=<daybucket>`).
- `window.NFOD.data` facade — views import from it.

### money_flow_data.json reshape (engine.py)
Computation identical — output shape only. Nested schema:

| Current (flat) | New (nested) |
|---|---|
| `participant_summary.fii_fut_net_change` | `participants.fii.futures.net` |
| `participant_summary.fii_ce_net_short_change` | `participants.fii.options.ce.netShort` |
| `participant_summary.smart_money_score` | `verdict.score` |
| `participant_summary.bias_label` | `verdict.bias` |
| `participant_summary.retail_trap_alarm` | `retail.trapAlarm` |
| `index_rolls.NIFTY.resistance_roll` | `rolls.NIFTY.resistance` |
| `stock_breadth.call_writing_bearish[]` | `breadth.callWriting[]` |
| `conviction_trends.NIFTY.strikes[]` | `conviction.NIFTY.strikes[]` |
| `flow_divergence[]` | `divergence[]` |

- Rewrite `verdict_payload` construction in `run_engine` to emit nested structure.
- `_nested()` helper maps flat participant dict → nested. Keep all computation identical.
- Schema-shape comment at top of JSON block documents structure.
- Breaking change — current site won't read new JSON. Fine: same release replaces frontend.
- GitHub Action unchanged.

### ApexCharts
- Still CDN. Charts read `ohlc_data.json` (unchanged) + embedded CSV.

## 5. New Features

### 5.1 Inline Sparklines
- Gross OI instrument tables (per participant row), KPI cards, verdict stance rows.
- Data: embedded CSV history, `net = long − short` per instrument, last 8 days.
- Tiny inline SVG `<polyline>`, no library (~20 lines). Color = latest-day direction.
- Hover tooltip = per-day net values. Generated once per date render, cached.

### 5.2 Advanced Date Picker
- Custom calendar popover: month grid, weekday headers, trading-date highlight, disabled non-trading days.
- ‹ prev / next month + month label. Quick presets: Latest, Prev week, Month expiry (last-Tuesday logic), Week ago.
- Keyboard: arrows, Enter, Esc. Header input + `‹` `›` steppers. Zero new deps.

### 5.3 Market Status Widget
- Pill: LIVE (green pulse) / CLOSED (gray) / PRE-MARKET / HOLIDAY.
- IST logic: Mon–Fri 09:15–15:30 LIVE; 09:00–09:15 PRE-MARKET; weekend CLOSED.
- Shows IST clock (24h ticking) + NIFTY spot from latest data.
- `ponytail:` — no holiday calendar now; add if worthwhile.

### 5.4 Export & Print
- "Export CSV" button per instrument table (client-side download).
- `@media print` stylesheet → clean single-page report of active date.

## 6. Component Structure, Error Handling, Testing

### Module layout
```
index.html          — shell, header, view containers, CDN links
styles.css          — design tokens, base, components, themes, responsive, print
data.js             — _EMBEDDED_CSV + parse + fetchers (cache-bust) + NFOD.data
app.js              — init, state (date, theme, activeView), header wiring
views/gross.js      — KPI cards + tables + right rail + takeaways
views/verdict.js    — banner, rolls, stance, conviction, divergence, breadth
views/charts.js     — ApexCharts wiring, range select, export PNG
lib/sparkline.js    — inline SVG sparkline renderer
lib/calendar.js     — date-picker popover
lib/utils.js        — formatIndianNum, sortDates, expiry math, clamp
```
Each view: `render(state)` + helpers; registers into `NFOD.views`. Views isolated from each other's DOM; data only via `NFOD.data`.

### Error handling
- Fetch failure → inline skeleton→error card + Retry. No silent blank.
- Parse failure → error card + console detail.
- ApexCharts CDN failure → "charts unavailable" fallback card.
- Date index clamped; missing data → `-`/empty state, never crash.
- `?debug=1` → hidden `#debug-log` panel (window.onerror).

### Testing (runnable, no framework)
- `test/smoke.html` loads real `data.js` + markup fragment; asserts:
  - CSV parses to expected date count & 4×6 grid.
  - `renderGrossOIDate()` fills correct `<tr>` count per table.
  - Date nav wraps; expiry-math helper correct.
  - `formatIndianNum` edge cases (0, negative, null, lakhs).
  - Verdict JSON maps to nested schema.
- Console prints PASS/FAIL. `ponytail:` — could upgrade to headless runner later.

## 7. Non-Goals (explicitly excluded)
- No new data sources.
- No framework/build step.
- No holiday calendar (noted ceiling).
- No server-side changes beyond engine.py output shape + fetcher.py boundary string.

## 8. Delivery Order
1. fetcher.py contract swap + data.js
2. styles.css design system
3. app.js shell + header + date picker + market status
4. views/gross.js + sparklines
5. views/verdict.js
6. views/charts.js
7. engine.py schema reshape
8. test/smoke.html
9. Manual QA on desktop/mobile, both themes
