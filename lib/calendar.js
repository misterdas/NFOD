/* Minimal calendar popover. No deps. */
window.NFOD = window.NFOD || {};
function createDatePicker({ anchor, dates, onSelect }) {
  const closeExisting = () => document.querySelector(".cal-popover")?.remove();
  closeExisting();
  const pop = document.createElement("div");
  pop.className = "cal-popover";
  const trading = new Set(dates);                 // "DD-MM-YYYY"
  const fmt = (d) => String(d.getDate()).padStart(2, "0") + "-" +
                 String(d.getMonth() + 1).padStart(2, "0") + "-" + d.getFullYear();
  let cursor = new Date();                        // view month
  const selected = dates[NFOD.state?.dateIndex || 0] || dates[0] || "";

  function render() {
    const y = cursor.getFullYear(), m = cursor.getMonth();
    const first = new Date(y, m, 1);
    const startDow = first.getDay();              // 0=Sun
    const daysInMonth = new Date(y, m + 1, 0).getDate();
    const monthLabel = cursor.toLocaleString("en-IN", { month: "long", year: "numeric" });
    let grid = "";
    const cells = [];
    for (let i = 0; i < startDow; i++) cells.push("");
    for (let d = 1; d <= daysInMonth; d++) cells.push(new Date(y, m, d));
    cells.forEach(dt => {
      if (!dt) { grid += `<span class="cal-cell"></span>`; return; }
      const key = fmt(dt);
      const isTrade = trading.has(key);
      const isSel = key === selected;
      grid += `<button class="cal-cell ${isTrade ? "tradable" : "dim"} ${isSel ? "selected" : ""}"
        ${isTrade ? "" : "disabled"}>${dt.getDate()}</button>`;
    });
    pop.innerHTML = `
      <div class="cal-head">
        <button class="btn btn-sm btn-ghost" id="cal-prev">‹</button>
        <span class="cal-label">${monthLabel}</span>
        <button class="btn btn-sm btn-ghost" id="cal-next">›</button>
      </div>
      <div class="cal-grid">
        ${["Su","Mo","Tu","We","Th","Fr","Sa"].map(d => `<span class="cal-dow">${d}</span>`).join("")}
        ${grid}
      </div>
      <div class="cal-presets">
        <button class="btn btn-sm" data-preset="latest">Latest</button>
        <button class="btn btn-sm" data-preset="week">Week Ago</button>
        <button class="btn btn-sm" data-preset="expiry">Month Expiry</button>
      </div>`;
    // stopPropagation: render() rewires pop.innerHTML, detaching the clicked button; without it
    // the document outside-click handler sees a detached target and closes the popover.
    pop.querySelector("#cal-prev").onclick = (e) => { e.stopPropagation(); cursor = new Date(y, m - 1, 1); render(); };
    pop.querySelector("#cal-next").onclick = (e) => { e.stopPropagation(); cursor = new Date(y, m + 1, 1); render(); };
    pop.querySelectorAll(".cal-cell.tradable").forEach(btn => {
      btn.onclick = () => pick(dates.indexOf(btn.textContent.trim().length ? fmt(new Date(y, m, +btn.textContent)) : null));
    });
    pop.querySelectorAll("[data-preset]").forEach(btn => {
      btn.onclick = () => {
        const n = dates.length;
        const idx = btn.dataset.preset === "latest" ? n - 1
          : btn.dataset.preset === "week" ? Math.max(0, (NFOD.state?.dateIndex ?? n - 1) - 5)
          : findExpiryIndex();
        pick(idx);
      };
    });
  }
  function findExpiryIndex() {
    let best = 0, bestDist = 1e9;
    const today = new Date();
    dates.forEach((d, i) => {
      const diff = NFOD.utils.daysToMonthlyExpiry(d);
      if (diff === null) return;
      const dist = Math.abs(diff);
      if (dist < bestDist) { bestDist = dist; best = i; }
    });
    return best;
  }
  function pick(idx) {
    closeExisting();
    if (idx >= 0 && idx < dates.length && onSelect) onSelect(idx);
  }
  render();
  anchor.after(pop);
  const onKey = (e) => {
    if (!pop.isConnected) { document.removeEventListener("keydown", onKey); return; }
    if (e.key === "Escape") closeExisting();
    else if (e.key === "ArrowLeft") { e.preventDefault(); cursor = new Date(cursor.getFullYear(), cursor.getMonth() - 1, 1); render(); }
    else if (e.key === "ArrowRight") { e.preventDefault(); cursor = new Date(cursor.getFullYear(), cursor.getMonth() + 1, 1); render(); }
  };
  const onDoc = (e) => {
    if (!pop.contains(e.target) && e.target !== anchor) {
      closeExisting();
      document.removeEventListener("click", onDoc);
      document.removeEventListener("keydown", onKey);
    }
  };
  document.addEventListener("click", onDoc);
  document.addEventListener("keydown", onKey);
  return pop;
}
