window.NFOD = window.NFOD || {};
NFOD.views = NFOD.views || {};
NFOD.state = { dateIndex: NFOD.data.availableDates.length - 1, dates: NFOD.data.availableDates, activeView: "gross", theme: "dark" };

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

NFOD.switchView = function switchView(name) {
  NFOD.state.activeView = name;
  document.querySelectorAll(".view").forEach(v => v.classList.toggle("active", v.id === "view-" + name));
  renderActiveView();
};
function renderActiveView() {
  const v = NFOD.state.activeView;
  if (NFOD.views[v] && typeof NFOD.views[v].render === "function") NFOD.views[v].render(NFOD.state);
}

function bindTheme() {
  const btn = $("#btn-theme");
  const apply = (t) => {
    NFOD.state.theme = t;
    document.body.classList.toggle("theme-light", t === "light");
    document.body.classList.toggle("theme-dark", t !== "light");
    if (NFOD.state.activeView === "charts" && NFOD.views.charts && NFOD.views.charts.render) NFOD.views.charts.render(NFOD.state);
  };
  apply("dark");
  btn.onclick = () => apply(NFOD.state.theme === "dark" ? "light" : "dark");
}

function bindMenu() {
  const btn = $("#btn-menu");
  const popover = $("#menu-popover");
  if (!btn || !popover) return;
  popover.innerHTML = `
    <button class="menu-item" data-view="gross" onclick="NFOD.switchView('gross'); $('#menu-popover').hidden=true;">Gross OI</button>
    <button class="menu-item" data-view="verdict" onclick="NFOD.switchView('verdict'); $('#menu-popover').hidden=true;">Verdict</button>
    <button class="menu-item" data-view="charts" onclick="NFOD.switchView('charts'); $('#menu-popover').hidden=true;">Charts</button>
  `;
  const syncActive = () => {
    popover.querySelectorAll(".menu-item").forEach(i =>
      i.classList.toggle("active", i.dataset.view === NFOD.state.activeView));
  };
  btn.onclick = (e) => {
    e.stopPropagation();
    if (popover.hidden) syncActive();
    popover.hidden = !popover.hidden;
  };
  document.addEventListener("click", (e) => {
    if (!popover.hidden && !popover.contains(e.target) && e.target !== btn) {
      popover.hidden = true;
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  bindTheme(); bindMenu(); renderDateNav();
  $("#footer-date").textContent = "Date: " + NFOD.getDate();
  try {
    renderActiveView();
  } finally {
    // Reveal views now that content is painted — same task, so the browser
    // cannot paint the empty shell in between (CLS guard, see styles.css).
    // finally: even if a view render throws, the page must never stay invisible.
    document.body.classList.add("ready");
  }
});

NFOD.debuglog = (msg) => {
  if (new URLSearchParams(location.search).get("debug") !== "1") return;
  const el = document.getElementById("debug-log");
  if (el) { el.hidden = false; el.textContent += "\n" + msg; }
};
window.addEventListener("error", (e) => NFOD.debuglog("ERROR: " + e.message));
