### Task 5: app.js — state, header, tabs, market status, theme

**Files:**
- Create: `app.js` (replaces existing)
- Consumes: `NFOD.data`, `NFOD.utils`, `NFOD.views` (registered by views), `createDatePicker` (Task 6 — stub call now).

**Interfaces:**
- Produces: `NFOD.state = { dateIndex, dates, activeView, theme }`, `NFOD.switchView(name)`, `NFOD.getDate()`, `renderHeader()`, `renderMarketStatus()`.

- [ ] **Step 1: Write app.js**

```js
window.NFOD = window.NFOD || {};
NFOD.views = NFOD.views || {};
NFOD.state = { dateIndex: 0, dates: NFOD.data.availableDates, activeView: "gross", theme: "dark" };

const $ = (sel, root) => (root || document).querySelector(sel);

function renderDateNav() {
  const s = NFOD.state;
  const wrap = $("#date-nav");
  const latest = s.dates.length - 1;
  wrap.innerHTML = `
    <button class="btn btn-sm btn-ghost" id="d-prev" aria-label="Previous">‹</button>
    <button class="btn btn-sm date-chip" id="d-picker">${s.dates[s.dateIndex]}</button>
    <button class="btn btn-sm btn-ghost" id="d-next" aria-label="Next">›</button>
    <button class="btn btn-sm" id="d-latest" ${s.dateIndex === latest ? "disabled" : ""}>Latest</button>`;
  $("#d-prev").onclick = () => setDate(clampIdx(s.dateIndex - 1));
  $("#d-next").onclick = () => setDate(clampIdx(s.dateIndex + 1));
  $("#d-latest").onclick = () => setDate(latest);
  $("#d-picker").onclick = (e) => {
    e.stopPropagation();
    createDatePicker({ anchor: $("#d-picker"), dates: s.dates, onSelect: setDate });
  };
}
function clampIdx(i) { return NFOD.utils.clamp(i, 0, NFOD.state.dates.length - 1); }
function setDate(i) { NFOD.state.dateIndex = i; renderDateNav(); $("#footer-date").textContent = "Date: " + NFOD.getDate(); renderActiveView(); }
NFOD.getDate = () => NFOD.state.dates[NFOD.state.dateIndex];

function switchView(name) {
  NFOD.state.activeView = name;
  document.querySelectorAll(".tab-btn").forEach(b => b.classList.toggle("active", b.dataset.view === name));
  document.querySelectorAll(".view").forEach(v => v.classList.toggle("active", v.id === "view-" + name));
  renderActiveView();
}
function renderActiveView() {
  const v = NFOD.state.activeView;
  if (NFOD.views[v] && typeof NFOD.views[v].render === "function") NFOD.views[v].render(NFOD.state);
}
function bindTabs() {
  document.querySelectorAll(".tab-btn").forEach(b => b.onclick = () => switchView(b.dataset.view));
}

/* Market status (IST) */
function istParts() {
  const now = new Date();
  const ist = new Date(now.getTime() + 330 * 60000);
  return { day: ist.getUTCDay(), h: ist.getUTCHours(), m: ist.getUTCMinutes() };
}
function marketStatus() {
  const { day, h, m } = istParts();
  if (day === 0 || day === 6) return { label: "CLOSED", live: false };
  const mins = h * 60 + m;
  if (mins >= 555 && mins < 570) return { label: "PRE-MARKET", live: false };
  if (mins >= 570 && mins <= 930) return { label: "LIVE", live: true };
  return { label: "CLOSED", live: false };
}
function renderMarketStatus() {
  const st = marketStatus();
  const el = $("#market-status");
  el.innerHTML = `<span class="status-pill ${st.live ? "live" : ""}">● ${st.label}</span>
    <span class="status-clock" id="ist-clock"></span>`;
  setInterval(() => {
    const { h, m } = istParts();
    $("#ist-clock").textContent = String(h).padStart(2, "0") + ":" + String(m).padStart(2, "0") + " IST";
  }, 1000);
}
function bindTheme() {
  const btn = $("#btn-theme");
  const apply = (t) => {
    NFOD.state.theme = t;
    document.body.classList.toggle("theme-light", t === "light");
    document.body.classList.toggle("theme-dark", t !== "light");
  };
  apply("dark");
  btn.onclick = () => apply(NFOD.state.theme === "dark" ? "light" : "dark");
}

document.addEventListener("DOMContentLoaded", () => {
  bindTabs(); bindTheme(); renderDateNav(); renderMarketStatus(); renderActiveView();
});
```

- [ ] **Step 2: Verify**

Open `index.html`: header date chips work (prev/next/latest wrap via clamp), tab switching toggles `.active`, theme toggle flips `body.theme-light`, market pill shows LIVE/CLOSED correctly for current IST, clock ticks. `createDatePicker` throws only if calendar.js missing — Task 6 adds it.

- [ ] **Step 3: Commit**

```bash
git add app.js
git commit -m "feat(app): shell state, tabs, theme, market status, date nav"
```

---

