# Task 8 Report — views/gross.js (Gross OI view)

**Status:** DONE
**Commit:** `7c0c859` feat(gross): KPI cards, instrument tables, sparklines, right rail, takeaways (branch `redesign/overhaul`)

## Implemented

Created `views/gross.js` (189 lines) verbatim from the task brief. Registers `NFOD.views.gross.render(state)`:
- 4 KPI cards: FII Index Futures (Net), Client Index Calls (Net), Pro Index Calls (Net), Institutional Bias (fii_futΔ + pro_ceΔ + pro_putΔ with put net sign-flipped to `pe_shortΔ − pe_longΔ`; thresholds ±20k → BULLISH/BEARISH/NEUTRAL / MIXED).
- 6 instrument tables (Index/Stock × Futures/Calls/Puts), each 4 participant rows (Client/DII/FII/Pro) with columns Longs Δ, Shorts Δ, Net Today, Today, 1D Ago, 2D Ago, Trend (8-day sparkline via `NFOD.sparkline`).
- Right rail "Today's Action": per-participant Bought/Sold cards over all 6 instruments.
- Key Takeaways loaded async from `docs/money_flow_data.json` `.participant_summary` (flat keys), appended below the grid.
- Export CSV buttons per table (data-URI download, named `<inst-id>-<date>.csv`).

## Verification

Headless Chrome (C:/Program Files/Google/Chrome/Application/chrome.exe) via Python playwright against real `index.html` served over HTTP (file:// blocks the JSON fetch). Script: `.superpowers/sdd/2026-08-01-redesign/verify_gross.py` (git-ignored).

Output — 27/27 checks passed:
```
expected: fii_fut=13499 cl_calls=-15758 pro_calls=23847 pro_puts=-204071 bias=-166725 bias_txt=BEARISH
PASS  initial view on latest date  31-07-2026
PASS  4 KPI cards
PASS  6 instrument tables
PASS  each table has 4 participant rows
PASS  sparkline column rendered (24 svgs)
PASS  right rail has 4 participant cards
PASS  takeaways async loaded
PASS  takeaway shows session date
PASS  KPI1 FII Index Futures net matches  13499 vs 13499
PASS  KPI2 Client Index Calls net matches  -15758 vs -15758
PASS  KPI3 Pro Index Calls net matches  23847 vs 23847
PASS  bias text matches  BEARISH vs BEARISH
PASS  bias score matches  -166725 vs -166725
PASS  bias card sign class  kpi-value pos-down
PASS  Index Futures FII Longs Δ matches  326 vs 326
PASS  date nav to prev updates chip  30-07-2026
PASS  date nav re-renders values  -6,975 != -13,173
PASS  sparklines re-rendered on nav
PASS  Latest returns to latest date  31-07-2026
PASS  latest restores original value  -13,173 == -13,173
PASS  Export CSV downloads file  index-futures-31-07-2026.csv
PASS  CSV content has 5 rows
PASS  only expected 404s (verdict/charts)
PASS  no page errors  []
PASS  no console errors  []
```

### Value cross-check (latest date 31-07-2026 vs prev 30-07-2026)

Computed from the external `FDCP_Data.csv` (source of the embedded data) in Python. NOTE: the first version of this table mis-transcribed the input operands for Client Calls, Pro Calls, and Pro Puts (rendered RESULTS were correct; shown arithmetic was not). Corrected below:

| KPI | Expected (FDCP_Data.csv) | Rendered | Match |
|---|---|---|---|
| FII Index Futures (Net) | (24761−24435) − (197874−211047) = 13499 | 13,499 | ✓ |
| Client Index Calls (Net) | (2558236−2275804) − (2534120−2235930) = −15758 | −15,758 | ✓ |
| Pro Index Calls (Net) | (892107−776587) − (736193−644520) = 23847 | 23,847 | ✓ |
| Pro Index Puts (Net) | (1105289−891141) − (1286439−868220) = −204071 | (used in bias) | ✓ |
| Institutional Bias | 13499 + 23847 + (−204071) = −166725 → BEARISH | BEARISH, −166,725 | ✓ |
| Index Futures FII Longs Δ | 24761 − 24435 = 326 | 326 | ✓ |

Bias math independently confirmed: Pro put SHORT rose 891141→1105289 (+214148) while Pro put LONG rose 868220→1286439 (+418219); long leg gained more, giving the negative put net (−204071) that drives the BEARISH bias.

## Files changed

- `views/gross.js` — created (only file committed).
- `.superpowers/sdd/2026-08-01-redesign/verify_gross.py` — verification script (git-ignored, not committed).

## Self-review

- Code is byte-identical to the brief; no edits made.
- No console errors besides expected `views/verdict.js` + `views/charts.js` 404s (Task 9/10).
- `styles.css` classes all present (verified `.spark-cell`, `.kpi-sub`, `.takeaways-title`, `.action-label`, `.rail-title`, `.compact` etc.).
- `lib/utils.js`, `data.js`, `lib/sparkline.js`, `app.js` interfaces match the brief's assumptions.
- Export CSV works; download filename + content verified.

## Concerns

1. **App default view is oldest date** (`app.js` line 3: `dateIndex: 0`), so on first load the gross view shows 02-06-2026 with null Δs and 1-point sparklines ("·" instead of an SVG line). Not a gross.js defect; downstream decide whether Task 5 should default to `dates.length - 1`. First-run experience on the real dashboard shows a mostly-empty grid.
2. **Export CSV columns are a subset** (Longs Δ, Shorts Δ, Net Today, Today, 1D Ago, 2D Ago where "Today"/"1D Ago" re-use the same long/short values and 2D Ago is hardcoded "-"). This is exactly what the brief specifies, but the CSV data is a weaker representation than the on-screen table. Flag if richer export desired later.
3. **Takeaways card loads on every render** (async insert) — clicking through dates re-appends the same takeaways block each render since `view.innerHTML` is replaced first; no duplicate accumulation. Confirmed no dupes in test.
4. `daysToMonthlyExpiry` runs against `ps.date` (latest 31-07-2026), which for a "Latest" date can be stale vs the date nav selection — matches brief behavior.
5. `views/` directory was absent before this task; created as part of the commit. `index.html` already referenced `views/gross.js`.

---

# Fix Report — Takeaway duplicate race on rapid date nav

**Status:** DONE
**Commit:** `fix(gross): stale-safe takeaways to prevent duplicate blocks on rapid nav` (append-only; see commits below)

## Finding (review)

Each `render()` called `loadMoneyFlow().then(cb)` and the callback appended to whatever `.dash-grid` existed at resolve time. On rapid date nav, render A's grid is synchronously replaced by render B, but both in-flight callbacks resolve into the newest grid → duplicate takeaways blocks. Cached-promise case double-fires too (two `.then` on one resolved promise).

## Fix

`views/gross.js` (uncommitted delta on top of `7c0c859`):
- module-scoped `let renderSeq = 0;`
- `render()` captures `const token = ++renderSeq;`
- async callback: `if (token !== renderSeq) return;` (stale render bails), and the append target is now `view.querySelector(".dash-grid")` (scoped to this view's node, not a global query).

Net effect: only the newest render's callback survives; stale callbacks are no-ops whether the grid was replaced or the promise was shared/cached.

## Verification (headless Chrome, real index.html)

`verify_gross.py` extended with a deterministic race A/B — `NFOD.data.loadMoneyFlow` is patched in-page to resolve 400 ms after each render call, so rapid nav (6 prev clicks, no waits) guarantees multiple in-flight callbacks overlap:

```
PASS  rapid nav: exactly one takeaways block  got 1
PASS  rapid nav: takeaways inside current grid
PASS  rapid nav: takeaways still show latest session
PASS  race A/B (delayed, fixed code): exactly one block  got 1
PASS  race A/B (delayed, pre-fix code): duplicates reproduce  got 2
```

The pre-fix code (`git show HEAD:views/gross.js`, served via route interception) reproduces the duplicate block under the same deterministic delay; the fixed code emits exactly one. Full suite: 31/31 PASS (structure, KPI values, sparklines, date nav re-render, single-nav one block, CSV export, only-expected 404s, no console errors).

## Corrected cross-check numbers (re-verified)

Re-verified rendered values against `FDCP_Data.csv` arithmetic (`.superpowers/sdd/2026-08-01-redesign/compute_crosscheck.py`). The rendered values were correct all along; the earlier report table's OPERANDS were mis-transcribed. Correct, re-confirmed:

| KPI | Computation | Rendered |
|---|---|---|
| FII Index Futures (Net) | (24761−24435) − (197874−211047) | 13499 |
| Client Index Calls (Net) | (2558236−2275804) − (2534120−2235930) | −15758 |
| Pro Index Calls (Net) | (892107−776587) − (736193−644520) | 23847 |
| Pro Index Puts (Net) | (1105289−891141) − (1286439−868220) | −204071 |
| Institutional Bias | 13499 + 23847 + (−204071) | −166725 → BEARISH |
| Index Futures FII Longs Δ | 24761 − 24435 | 326 |

## Commits (this task)

- `7c0c859` feat(gross): KPI cards, instrument tables, sparklines, right rail, takeaways (original, before fix)
- `8a4cbd9` fix(gross): stale-safe takeaways to prevent duplicate blocks on rapid nav

## Concerns (post-fix)

1. `renderSeq` is module-scoped per view instance; token monotonic within the page lifetime — no reset needed since it only ever compares last-wins.
2. Takeaways text always reflects the money-flow file's latest date regardless of selected grid date (data model limitation, unchanged by fix) — rapid-nav test asserts the block is inside the current grid and session text is present.
3. The 6-prev rapid loop ends on 23-07-2026, so the CSV export check after it exports `index-futures-23-07-2026.csv` — correct behavior (filename follows selected date).
