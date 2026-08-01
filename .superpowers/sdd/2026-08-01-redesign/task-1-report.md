# Task 1 Report: lib/utils.js — shared helpers

**Status:** DONE

## What I implemented

Created `lib/utils.js` (46 lines) verbatim from the brief. Pure-function module under `NFOD.utils` namespace:

- `formatIndianNum(v)` — en-IN locale formatting, `-` for null/undefined/NaN, `"0"` for zero, negative sign prepended.
- `clamp(v, min, max)`
- `_key(d)` — private: `DD-MM-YYYY` → `YYYYMMDD` string for comparison.
- `sortDatesChronological(dates)` — non-mutating (`.slice()`), string-key sort.
- `daysToMonthlyExpiry(dStr)` — last-Tuesday-of-next-month proxy (mirrors `renderGrossOITakeaways()`), returns day diff or `null` on parse error.
- `monthlyExpirySuffix(days)` — expiry-day messaging for the 0..5 / -7..-1 bands.
- `cacheBust(url)` — appends `?d=` or `&d=` day-bucket token.
- `window.NFOD = window.NFOD || {}` guard so multiple scripts can extend the namespace.

## Verification

Loaded file with Node 24 via `require("vm").runInThisContext` with `global.window = global` shim (browser-faithful: `window` is the global object; the earlier `window = {}` object-shim failed because `NFOD` isn't hoisted onto it).

Command:
```
node -e '...' (vm loader + 9 assert checks)
```

Output:
```
check 1: true ... check 9: true
ALL PASS: true
daysToMonthlyExpiry 31-07-2026: -3
suffix -5: | 5 Days Post Monthly Expiry
```

Covered all 6 brief check expressions plus 3 extra:
- `sortDatesChronological(["03-07-2026","01-07-2026","02-07-2026"])` → `["01-07-2026","02-07-2026","03-07-2026"]` (brief's explicit requirement)
- `cacheBust("data.csv")` starts with `data.csv?d=` and `cacheBust("data.csv?x=1")` contains `&d=`
- `daysToMonthlyExpiry("31-07-2026")` = `-3`, `monthlyExpirySuffix(-5)` = `| 5 Days Post Monthly Expiry`

## Files changed

- Added: `lib/utils.js` (directory `lib/` created)

## Commit

`82792b7` — `feat(utils): shared formatting/date helpers` (branch `redesign/overhaul`)

## Self-review notes

- File byte-for-byte matches the brief spec; no deviations.
- `monthlyExpirySuffix` has two overlapping branches for `days === 2` (`in 2 Days` and `in 2-5 Days`) — dead first check is unreachable but harmless; kept verbatim per spec.
- LF→CRLF line-ending warning from git is cosmetic; `.gitattributes`/`core.autocrlf` untouched.

## Concerns

- None blocking. `daysToMonthlyExpiry` result depends on Node's `new Date(y, m, d)` (local-timezone) — identical to browser behavior for this use, no TZ risk since construction is local and diff is whole days via `Math.round`.
- Node harness used `vm.runInThisContext`, not `require`, because CJS module scope would isolate `NFOD` from global. Not a code change; browser `<script>` load is unaffected.
