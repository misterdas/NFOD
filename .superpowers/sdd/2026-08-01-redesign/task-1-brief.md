### Task 1: lib/utils.js — shared helpers + smoke tests

**Files:**
- Create: `lib/utils.js`
- Test: `test/smoke.html` (created in Task 12; here just assert utils via a temporary inline check)

**Interfaces:**
- Produces: `formatIndianNum(v)`, `sortDatesChronological(dates)`, `daysToMonthlyExpiry(dStr)`, `monthlyExpirySuffix(days)`, `clamp(v,min,max)`, `cacheBust(url)`, `NFOD.utils` namespace.

- [ ] **Step 1: Create `lib/utils.js`**

```js
/* Shared helpers — pure functions, no DOM, no fetch. */
window.NFOD = window.NFOD || {};
NFOD.utils = (function () {
  function formatIndianNum(v) {
    if (v === null || v === undefined || isNaN(v)) return "-";
    if (v === 0) return "0";
    const abs = Math.abs(v).toLocaleString("en-IN");
    return v < 0 ? "-" + abs : abs;
  }
  function clamp(v, min, max) { return Math.max(min, Math.min(max, v)); }
  // CSV dates "DD-MM-YYYY" → comparable "YYYYMMDD"
  function _key(d) { const [dd, mm, yy] = String(d).split("-"); return yy + mm + dd; }
  function sortDatesChronological(dates) {
    return dates.slice().sort((a, b) => {
      const ka = _key(a), kb = _key(b);
      return ka < kb ? -1 : ka > kb ? 1 : 0;
    });
  }
  // Mirrors renderGrossOITakeaways(): last-Tuesday proxy for monthly expiry.
  function daysToMonthlyExpiry(dStr) {
    try {
      const [dd, mm, yy] = String(dStr).split("-");
      const d0 = new Date(+yy, +mm - 1, +dd);
      const y = d0.getFullYear(), m = d0.getMonth() + 1;
      const nextFirst = new Date(y + (m === 12 ? 1 : 0), m % 12, 1);
      const daysBack = ((nextFirst.getDay() - 2) % 7 + 7) % 7 || 7;
      const expiry = new Date(nextFirst.getTime() - daysBack * 864e5);
      return Math.round((expiry - d0) / 864e5);
    } catch (e) { return null; }
  }
  function monthlyExpirySuffix(days) {
    if (days === null || days === undefined) return "";
    if (days === 0) return "| Monthly Expiry Today";
    if (days === 1) return "| Monthly Expiry Tomorrow";
    if (days === 2) return "| Monthly Expiry in 2 Days";
    if (days >= 2 && days <= 5) return "| Monthly Expiry in " + days + " Days";
    if (days === -1) return "| Post Monthly Expiry";
    if (days >= -7 && days <= -2) return "| " + Math.abs(days) + " Days Post Monthly Expiry";
    return "";
  }
  function cacheBust(url) {
    const sep = url.includes("?") ? "&" : "?";
    return url + sep + "d=" + Math.floor(Date.now() / 864e5);
  }
  return { formatIndianNum, clamp, sortDatesChronological, daysToMonthlyExpiry, monthlyExpirySuffix, cacheBust };
})();
```

- [ ] **Step 2: Verify helpers**

Open a browser console (or `node -e` with the file) and run:

```js
NFOD.utils.formatIndianNum(-180398) === "-1,80,398"
NFOD.utils.formatIndianNum(0) === "0"
NFOD.utils.formatIndianNum(null) === "-"
NFOD.utils.clamp(200, -150, 150) === 150
NFOD.utils.daysToMonthlyExpiry("31-07-2026") !== null
NFOD.utils.monthlyExpirySuffix(3) === "| Monthly Expiry in 3 Days"
```

Expected: all `true`.

- [ ] **Step 3: Commit**

```bash
git add lib/utils.js
git commit -m "feat(utils): shared formatting/date helpers"
```

---

