# Task 4 Report: index.html — new app shell

**Status: DONE_WITH_CONCERNS** (see Concern 1 — pre-existing, out of Task 4 scope)

## What was implemented

Replaced the old `index.html` (full old dashboard markup) with the new shell, copied verbatim from `task-4-brief.md`:

- `<!DOCTYPE html>`, `<head>` with viewport, title `OI Analysis — Participant OI Dashboard`, favicon, Google Fonts (Inter + JetBrains Mono), `styles.css` link.
- `<body class="theme-dark">`
- `#header.app-header`: `.brand` (`.brand-mark`, `.brand-text` with h1 + `.brand-sub`), `#date-nav.header-center`, `#market-status.status-wrap`, `#btn-theme`, `#btn-menu`, `#menu-popover`.
- `#tab-bar` with 3 `.tab-btn` buttons (`data-view=gross|verdict|charts`), Gross OI active.
- `main.app-main` with `#view-gross.view.active`, `#view-verdict.view`, `#view-charts.view`.
- `footer.app-footer`: Gopal Das, `#footer-date` ("Date: --"), "NFD Participant OI Engine v3.0".
- `#debug-log[hidden]`.
- Script tags in exact brief order: `lib/utils.js` → `data.js` → `lib/sparkline.js` → `lib/calendar.js` → `views/gross.js` → `views/verdict.js` → `views/charts.js` → `app.js`.

No other file modified.

## Verification

Headless Chrome (`C:/Program Files/Google/Chrome/Application/chrome.exe`) via python-playwright, `file://` URL.

### Shell checks (full page load)

| Check | Result |
|---|---|
| title | `OI Analysis — Participant OI Dashboard` |
| `#header.app-header` present | true |
| `.brand h1` text | `OI Analysis` |
| tabs | `Gross OI`, `Verdict`, `Charts` |
| view sections (`#view-gross/.view`, `#view-verdict/.view`, `#view-charts/.view`) | 1 each |
| `.view.active` count | 1 (gross active) |
| `#footer-date` | `Date: --` |
| `#debug-log` present | true |
| script order in DOM | utils → data → sparkline → calendar → gross → verdict → charts → app |

### data.js syntax/API check

data.js verified in strict isolation (minimal HTML, only `lib/utils.js` + `data.js`; no app.js, no views):

- `window.NFOD.utils` object: true
- `window.NFOD.data` object: true
- `availableDates` is an **Array** (not a function) — length 43, `02-06-2026` … `31-07-2026`
- `getParticipantMap` returns `Client,DII,FII,Pro,TOTAL`
- `loadMoneyFlow`, `loadOHLC`, `parseCSV` all `function`
- `rawCSVData` parsed length: 215
- **Console errors: none**

### Expected errors (full page load)

5× `net::ERR_FILE_NOT_FOUND` — exactly the 5 not-yet-created scripts: `lib/sparkline.js`, `lib/calendar.js`, `views/gross.js`, `views/verdict.js`, `views/charts.js`. Expected per brief; Tasks 6–10 create them.

## Concerns

1. **`Identifier 'rawCSVData' has already been declared` pageerror on full load.** Root cause: old `app.js` (Task 5 replaces it) declares its own `let rawCSVData` and `var _EMBEDDED_CSV` at top level, colliding with `data.js`'s `let rawCSVData`. Confirmed NOT data.js's fault — data.js loads clean with zero errors in isolation, and the collision disappears the moment old app.js is not loaded. Out of Task 4 scope. Task 5 (new app.js) removes the duplicate declarations. Not a blocker; do not "fix" by touching data.js.
2. `availableDates` in data.js is an array property, not a function. `lib/calendar.js` / `views/*` (Tasks 6–10) must use it as `NFOD.data.availableDates` (array), not `availableDates()`. Flagging so Task 6+ authors read it correctly.
3. Old app.js referenced with no version query (`app.js?v=3.1` in old HTML) — new shell drops the query string; browser caching not an issue in this repo's deployment model.

## Files changed

- `index.html` (replaced) — committed.

## Self-review

- Shell matches brief byte-for-byte; script order preserved.
- All container IDs the views populate (`#header`, `#date-nav`, `#market-status`, `#tab-bar`, `#view-gross`, `#view-verdict`, `#view-charts`, `#footer`, `#debug-log`) present and matched against `styles.css` classes (app-header, brand, brand-mark, brand-text, brand-sub, header-center, header-right, status-wrap, btn, btn-icon, tab-bar, tab-btn, view/.active, app-footer, menu-popover, debug-log all exist in styles.css).
- `styles.css` loaded (no stylesheet error in console).
