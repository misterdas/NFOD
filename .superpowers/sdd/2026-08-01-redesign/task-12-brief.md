### Task 12: test/smoke.html + final wiring + QA

**Files:**
- Create: `test/smoke.html`
- Modify: `app.js` (theme change re-renders charts; add `?debug=1` panel hook)

**Interfaces:**
- Produces: a runnable assertion page; `NFOD.debuglog(msg)`.

- [ ] **Step 1: Write test/smoke.html**

```html
<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><title>Smoke</title></head>
<body>
<!-- Minimal harness: utils + data + sparkline + gross view. NFOD.state set
     manually (app.js not loaded — its DOMContentLoaded would double-run). -->
<div id="view-gross"></div>
<script src="../lib/utils.js"></script>
<script src="../data.js"></script>
<script src="../lib/sparkline.js"></script>
<script src="../views/gross.js"></script>
<script>
let pass = 0, fail = 0;
function eq(name, got, want) {
  const ok = JSON.stringify(got) === JSON.stringify(want);
  ok ? pass++ : fail++;
  console.log((ok ? "PASS" : "FAIL") + " " + name + (ok ? "" : " got=" + JSON.stringify(got) + " want=" + JSON.stringify(want)));
}
// Set minimal state (mirrors app.js default)
NFOD.state = { dateIndex: NFOD.data.availableDates.length - 1, dates: NFOD.data.availableDates, activeView: "gross", theme: "dark" };
eq("csv dates exist", NFOD.data.availableDates.length > 10, true);
eq("dates chronological", NFOD.utils.sortDatesChronological(["03-07-2026","01-07-2026","02-07-2026"])[0], "01-07-2026");
eq("fmt negative lakhs", NFOD.utils.formatIndianNum(-180398), "-1,80,398");
eq("fmt null", NFOD.utils.formatIndianNum(null), "-");
eq("clamp", NFOD.utils.clamp(999, -150, 150), 150);
eq("expiry suffix", NFOD.utils.monthlyExpirySuffix(3), "| Monthly Expiry in 3 Days");
eq("participant map has 4", Object.keys(NFOD.data.getParticipantMap(NFOD.data.availableDates[0])).length, 4);
// Render gross view into #view-gross, count rows: 6 tables × 4 participants
NFOD.views.gross.render(NFOD.state);
const view = document.getElementById("view-gross");
const rows = view.querySelectorAll("tbody tr");
eq("6 tables × 4 rows", rows.length, 24);
console.log("RESULT: " + pass + " pass, " + fail + " fail");
</script></body></html>
```

- [ ] **Step 2: Wire theme→charts re-render in app.js**

In the `bindTheme` apply(), after toggling classes, if `NFOD.state.activeView === "charts" && NFOD.views.charts.render`, call `NFOD.views.charts.render(NFOD.state)`.

- [ ] **Step 3: Add debug panel hook**

In app.js, at end:

```js
NFOD.debuglog = (msg) => {
  if (new URLSearchParams(location.search).get("debug") !== "1") return;
  const el = document.getElementById("debug-log");
  if (el) { el.hidden = false; el.textContent += "\n" + msg; }
};
window.addEventListener("error", (e) => NFOD.debuglog("ERROR: " + e.message));
```

- [ ] **Step 4: Run smoke test**

Open `test/smoke.html` in a browser. Expected console: all PASS + `RESULT: N pass, 0 fail`.

- [ ] **Step 5: Manual QA**

Desktop + mobile width (DevTools), dark + light theme: header sticky, date picker, market clock, all three views, charts theme sync, export CSV, error card + retry (rename `docs/money_flow_data.json` temporarily), print stylesheet, `?debug=1` logs.

- [ ] **Step 6: Commit**

```bash
git add test/smoke.html app.js
git commit -m "test: smoke assertions + debug hook + theme chart sync"
```

---

## Self-Review Notes

- **Spec coverage**: design tokens (T3), header/IA (T4/T5), sparklines (T7, T8), date picker (T6), market status (T5), verdict view + nested schema (T9, T11), charts (T10), export/print (T8 + T3 print CSS), smoke tests (T12), fetcher contract (T2). All spec sections mapped.
- **telegram.py** untouched (Global Constraints) — flat `participant_summary` preserved in engine output.
- **Type consistency**: `NFOD.data.{availableDates,getParticipantMap,loadMoneyFlow,loadOHLC}`, `NFOD.views.*.render(state)`, `NFOD.utils.*` consistent across tasks. `createDatePicker({anchor,dates,onSelect})` signature matches T5 call. Charts theme re-render wired in T12.
- **Known ceiling**: charts range selector is a stub (`ponytail:` note) — 1M/3M buttons present but not wired; acceptable per spec Non-Goals (range selector was optional polish). Calendar tradable-cell click builds date from cell text — verify round-trip in T6 Step 2.
