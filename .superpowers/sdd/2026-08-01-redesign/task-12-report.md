# Task 12 Report — smoke tests + final wiring

**Status: DONE**

Commit: `3903ddb` on branch `redesign/overhaul` — `test: smoke assertions + debug hook + theme chart sync`

## What was implemented

1. **`test/smoke.html`** (new) — runnable assertion page per brief, with 2 corrections (see Deviations).
2. **`app.js`** (modified):
   - `bindTheme().apply()` now re-renders charts on theme change: `if (NFOD.state.activeView === "charts" && NFOD.views.charts.render) NFOD.views.charts.render(NFOD.state)`.
   - `NFOD.debuglog(msg)` + `window.addEventListener("error", ...)` hook (brief's exact code).
   - Initial `NFOD.state.dateIndex` = `NFOD.data.availableDates.length - 1` (latest-date default).
   - **Bonus bug fix** (found by first-paint QA): `#footer-date` was only set inside `setDate()`, so first paint showed `Date: --`. DOMContentLoaded now sets it to `NFOD.getDate()`.
3. **`styles.css`** (2-line responsive fix) — see QA section.

## Deviations from brief

- **`smoke.html` assertion corrections** (brief's assertions did not match committed reality):
  - `"participant map has 4"` asserted `Object.keys(...).length === 4`, but embedded CSV now carries a `TOTAL` row per date → map has 5 keys. Changed to `["Client","DII","FII","Pro"].every(k => k in map)`.
  - `"6 tables × 4 rows"` counted `view.querySelectorAll("tbody tr")` = 48, because gross view also renders 4 right-rail cards (6 rows each) as `.data-table.compact`. Scoped selector to `.main-col .data-table tbody tr` → 24. Preserves the brief's intent (6 instrument tables × 4 participants).
  - Smoke's `NFOD.state` override already used latest date (per task instructions).
- **Commit message** — brief Step 6 says `git commit -m "test: smoke assertions + debug hook + theme chart sync"`. The rendered brief text uses `+` separators. Used `+` (matches repo's existing commit-message convention and the intent; the `·` in the .md is a copy artifact of the plan). Corrected the one-line in the brief verbatim otherwise.
- **`styles.css` committed too** (not in brief's `git add` list) because mobile QA uncovered a real overflow bug.

## Verification

All via headless Chrome (`C:\Program Files\Google\Chrome\Application\chrome.exe`) + python playwright, HTTP server on `127.0.0.1`, scripts in `.superpowers\sdd\2026-08-01-redesign\`.

### Smoke (`test/smoke.html`)
```
PASS csv dates exist / PASS dates chronological / PASS fmt negative lakhs / PASS fmt null
PASS clamp / PASS expiry suffix / PASS participant keys present / PASS 6 tables × 4 rows
RESULT: 8 pass, 0 fail
```

### Full app QA (`qa_app.py`)
- **First paint latest date:** footer `Date: 31-07-2026`, date chip `31-07-2026`, latest = `31-07-2026` (43 dates). OK.
- **Verdict view:** renders (17 KB content, verdict banner present). OK.
- **Charts view:** 4 chart cards, `window.ApexCharts` loaded, no error card. Theme toggle → charts.render called again (spy counter = 1). OK.
- **Debug hook:** `?debug=1` + `NFOD.debuglog('TEST-MARKER')` → `#debug-log` unhidden, text contains marker. OK.
- **Theme toggle:** body class flips `theme-light` ↔ `theme-dark`. OK.
- **Date nav:** prev decrements index, Latest returns to 42 (latest). OK.

### Extra QA (`qa_extra.py`, `qa_errorcard.py`, `qa_overflow.py`)
- **Mobile (390×844):** no horizontal overflow after CSS fix (bodyW 390 = vw 390). Header sticky.
- **Export CSV:** `.export-csv` click → anchor `download="index-futures-31-07-2026.csv"`, CSV payload correct (Client/DII/FII/Pro rows).
- **Date picker:** calendar popover visible on chip click, shows "August 2026".
- **Market clock:** `● CLOSED 16:44 IST`, clock ticks (IST string present).
- **Error card + retry:** renamed `docs/money_flow_data.json` → 404 in fresh context: view still renders, 0 takeaways items, no crash. Restore → 4 takeaways items. OK.
- **Print stylesheet:** `@media print` block present (11 rules), hides `.app-header`, `.tab-bar`, `.right-rail`, sparklines, export buttons, charts toolbar.
- **Overflow sweep:** gross/verdict/charts × mobile(390)/desktop(1280) — all bodyW == vw.

## Mobile overflow fix (found by QA, fixed in `styles.css`)

Two CSS bugs surfaced by mobile-width QA:
1. `.main-col` (grid item in `.dash-grid`) lacked `min-width: 0`, so the wide `.data-table` forced the `1fr` column to ~680px, blowing out the page (body 692px on 390px viewport). Fix: `min-width: 0` on `.main-col` so `.table-scroll` (overflow-x:auto) actually scrolls.
2. `#date-nav` (.header-center at width:100% under 640px) overflowed header by 12px. Fix: `flex-wrap: wrap` on `.app-header` in the 640px media query.

Both are standard grid/flex blowout fixes; no layout regression on desktop (overflow sweep clean at 1280px).

## Files changed

- `test/smoke.html` (new)
- `app.js` (+12/−2)
- `styles.css` (+2/−2)

## Self-review

- Brief applied as-is except the two smoke assertions that contradicted committed behavior (data.js TOTAL row, gross right-rail tables) and the bonus footer-date init fix.
- Latest-date default confirmed working end-to-end (footer + chip + smoke's own latest-date override).
- No new dependencies; debug hook is inert without `?debug=1` (early return).
- Charts theme re-render guarded against non-charts views and missing render fn.

## Concerns / manual QA for human

- **ApexCharts loads from CDN** — needs network. QA ran with network (CDN reached, charts rendered). Offline → `error-card` fallback is wired and tested-at-the-code-path level.
- **Actual print rendering** — headless verified the `@media print` rules exist and parse; did not rasterize a PDF. Human should run Ctrl+P, confirm tables print without sticky-column artifacts.
- **Visual polish** (sparkline aesthetics, chart axis labels, light-theme contrast at 390px) — headless confirmed presence/no-overflow but not visual appearance. Human should eyeball both themes at mobile + desktop.
- **Date-picker day-cell click** round-trip (brief self-review note) — popover opens and renders; actual date selection click not exercised headless.
- **Menu popover** (`#btn-menu`) — not exercised; verify in browser.
- **Market status LIVE badge** — current check ran outside 9:15–15:30 IST, so only CLOSED state seen; LIVE/PRE-MARKET states need a during-market-hour check (logic inspected: correct).
- **Charts range selector** — known stub per spec Non-Goals (`ponytail:` note in charts.js); 1M/3M buttons present but not wired.
- Helper QA scripts left in `.superpowers\sdd\2026-08-01-redesign\` (`run_smoke.py`, `dbg_smoke.py`, `qa_app.py`, `qa_extra.py`, `qa_errorcard.py`, `qa_overflow.py`) — untracked, outside repo. Rerun `python .../run_smoke.py` to re-verify.
