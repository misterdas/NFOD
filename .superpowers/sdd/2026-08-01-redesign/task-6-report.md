# Task 6 Report: lib/calendar.js — advanced trading-date picker

## Status: DONE_WITH_CONCERNS

## What I implemented

Created `lib/calendar.js` exactly per the brief (`createDatePicker({anchor, dates, onSelect})`), plus two fixes (see Bugs Found). index.html already referenced `lib/calendar.js` (line 48) so no wiring change needed.

`app.js`'s `#d-picker` handler (`createDatePicker({anchor: $("#d-picker"), dates: s.dates, onSelect: setDate})`) now works — the previous `createDatePicker is not defined` error is resolved. The picker uses the `dates` param passed from `s.dates`, not a stale global; `selected` computed from `dates[NFOD.state?.dateIndex || 0]`.

## Bugs found in the brief's code — both fixed

1. **Prev/next navigation destroyed the popover.** `render()` reassigns `pop.innerHTML`, detaching the clicked ‹/› button before its handler runs `render()`. The document-level outside-click listener (`onDoc`) then sees `e.target` (the detached button) is not inside `pop` and not the anchor → closes the popover. So clicking ‹ or › re-rendered then immediately closed. Fixed by adding `e.stopPropagation()` to both prev and next handlers so the document listener never fires for them.
2. **Esc-close was missing.** The task and brief verify both require "Esc/outside-click closes", but the brief's code only had the outside-click listener. Added a minimal `keydown` Escape handler that closes and removes itself.

## Verification (headless Chrome, Playwright, real index.html)

Script: `.superpowers/sdd/2026-08-01-redesign/verify_calendar.py` (temp, uncommitted).

```
PASS data loaded  [n=43]
PASS dates sorted DD-MM-YYYY
PASS first/last  [02-06-2026 .. 31-07-2026]
PASS popover opens, label=current month  ['August 2026']
PASS prev month works  [tradable=23]
PASS non-trading days dim/disabled  [dim=8]
PASS cell click round-trip -> 28-07-2026  [chip=28-07-2026 idx=39]
PASS footer date updated  [Date: 28-07-2026]
PASS Latest preset -> last date  [chip=31-07-2026 last=31-07-2026]
PASS Week Ago preset -> -5  [chip=24-07-2026 exp=24-07-2026]
PASS Month Expiry preset -> trading date  [chip=30-06-2026]
PASS Month Expiry preset -> correct date  [chip=30-06-2026 exp=30-06-2026]
PASS next month works  [October 2026]
PASS outside click closes
PASS Esc closes
PASS dimmed cell not selectable  [chip=30-06-2026]
==== SUMMARY ==== 16/16 passed
```

**Round-trip check (brief's concern):** the tradable-cell handler builds `fmt(new Date(y, m, +btn.textContent))` from the cell's day number + `cursor` month/year. Verified clicking day `28` in July 2026 yields `28-07-2026`, `NFOD.state.dateIndex === 39`, chip and footer both update. **No bug in the round-trip.** The day is parsed as `+btn.textContent` (number → `new Date(y, m, d)` normalizes correctly even for the currently-viewed month; no DST-day shift concern because the month/year come from `cursor`, not from `Date` arithmetic).

**Month Expiry preset correctness:** independent check reproduced `findExpiryIndex` logic → `30-06-2026` (closest date to the June monthly expiry per `daysToMonthlyExpiry`'s last-Tuesday proxy). Matches.

## Files changed

- Created: `C:\Users\Surajit Pakira\Documents\NFOD\lib\calendar.js` (86 lines)
- (Temp, uncommitted) `C:\Users\Surajit Pakira\Documents\NFOD\.superpowers\sdd\2026-08-01-redesign\verify_calendar.py`

## Commit

`f4360b8` feat(calendar): advanced trading-date picker with presets (on branch `redesign/overhaul`)

## Self-review

- Picker reads `dates` (the param), never a stale global; `NFOD.state?.dateIndex` only used for `selected`/preset anchoring, both guarded.
- `pick()` validates `0 <= idx < dates.length` before calling `onSelect`.
- Only `lib/calendar.js` committed; the verify script and report live under `.superpowers/sdd/` (untracked, not in the commit).
- No runnable unit test left behind — the Playwright script IS the runnable check and is kept in the redesign folder for the smoke-test task (12) to reuse.

## Concerns

1. **Esc handler not in the brief's code** — I added it (verify required it). If a later task's copy-paste from the brief overwrites the file, it will be lost. Note for Task 12 smoke test.
2. **4 `net::ERR_FILE_NOT_FOUND` console errors** on load: `lib/sparkline.js`, `views/gross.js`, `views/verdict.js`, `views/charts.js` don't exist yet (Tasks 7–10). Non-blocking for this task; `renderActiveView()` no-ops on missing views. Will disappear as later tasks land.
3. `cursor` always starts at "today" (current month), not at the selected date's month. Per brief spec; acceptable but the picker opens on a month with no trading days during weekends. Not changed — brief verbatim.
4. LF→CRLF warning on commit is cosmetic (core.autocrlf); no content impact.

---

## Fix report (Important review finding: arrow-key month nav)

**Finding:** spec requires "Keyboard: arrows/Esc"; the initial implementation had Esc only. Also, `onDoc`'s outside-click cleanup did not remove the keydown listener, so a stale handler could linger after outside-click close.

**Fix applied** (`lib/calendar.js`):
- Consolidated the two keydown paths (Esc + arrows) into ONE `onKey` handler on the document:
  - `Escape` → close
  - `ArrowLeft` → previous month (`cursor` −1 month, same as `#cal-prev`), with `e.preventDefault()`
  - `ArrowRight` → next month (same as `#cal-next`), with `e.preventDefault()`
- `onDoc` outside-click cleanup now removes BOTH `click` and `keydown` listeners.
- Added a self-heal guard in `onKey`: if the popover is no longer connected (`pop.isConnected === false`), remove the handler on next keystroke — belt-and-braces so a missed cleanup can't linger.

Note: the coordinator's `b1ef832 fix(plan): add arrow-key month nav to calendar` updated the plan; I merged the arrow logic into the existing `onDoc`+`onEsc` structure per instructions (single shared keydown handler + cleanup removal).

**Re-verification** (headless Chrome, Playwright, same harness + 4 new checks):

```
PASS ArrowLeft -> previous month  [July 2026]
PASS ArrowRight -> next month  [August 2026]
PASS arrow nav keeps popover open
PASS no stale keydown after outside-close
==== SUMMARY ==== 20/20 passed
```

All prior 16 checks still pass (cell round-trip, 3 presets, prev/next buttons, Esc, outside-click, dimmed-cell inert).

**Commit:** `22ac8e1` fix(calendar): arrow-key month nav, unified keydown cleanup (lib/calendar.js only; 14 insertions, 3 deletions).
