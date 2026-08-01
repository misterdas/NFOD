# Task 3 Report — styles.css design-token system

**Status:** DONE

## What was implemented

Created `C:\Users\Surajit Pakira\Documents\NFOD\styles.css` (563 lines). NOTE: a prior session had already written a complete `styles.css` for this task; this run verified it against the brief, added one missing selector, and committed it.

### Step 1 — Token layer (verbatim from brief)
- `:root` dark default palette + `body.theme-light` override block, copied exactly from the brief (fonts, spacing scale, radii, shadows, easing/duration, surface/border/text/semantic/accent/header colors).
- Added a `body.theme-dark` empty rule with a comment explaining `:root` is default; exists only to pair with `theme-light` (JS toggles classes).

### Step 2 — Base + component classes
- **Base/reset:** `*{box-sizing}` reset, `[hidden]`, `body{font:13px/1.5 var(--font-sans)}`, `.mono,.font-mono`, `.muted`, `.pos-up/.pos-down`, focus-visible, webkit scrollbar styling.
- **All brief component classes present** (verified via grep, 1 added this run):
  - `.kpi-card` / `.kpi-header` / `.kpi-value` (+ `.pos-up/.pos-down` colors)
  - `.instrument-block` / `.block-header`
  - `.data-table` — full-width, `th` surface-3 10px uppercase, `td` mono 11.5px, sticky thead (`position:sticky;top:0;z-index:3`), row hover, group-column separators via `th/td:nth-child(3n){border-left}`, `.compact` modifier, `.strike` accent
  - `.total-row`, `.sticky-col-first` (sticky left col with correct z-index layering under thead)
  - `.badge` + `.bullish/.bearish/.neutral/.caution`(alias `.warn`), `.pill` + `.pill-green/.red/.yellow/.purple`
  - `.btn` + `.primary`(accent-grad)/`.secondary`/`.ghost`/`.icon` + `.btn-sm`
  - `.select`, `.skeleton` (shimmer gradient), `.error-card` + `.retry-btn`
  - `.tab-bar` / `.tab-btn` / `.tab-btn.active`
  - `.date-chip`, `.sparkline` / `.sparkline-empty`
  - `.status-pill` + `.status-pill.live` (pulse)
  - `.verdict-gauge` (accent-grad background-clip:text big score) + `@supports not` fallback, `.pos-up/.pos-down` gradient variants
  - `.toast` (fixed bottom center), `.menu-popover` (absolute dropdown + child styling)
  - `.takeaways` / `.takeaway-item`
  - `.right-rail` / `.rail-card`, `.section-label` + `.fii/.pro/.dii`
  - `.stat-row` / `.stat-label` / `.stat-value`
  - `.roll-card` + `.bullish/.bearish`, `.roll-symbol`/`.roll-meta`/`.magnet`/`.roll-cells`/`.roll-label`/`.roll-desc`/`.trap`
  - `.conv-tabs`, `.breadth-grid` + `.breadth-col`/`.breadth-head`
  - `.divg-list`/`.divg-item`/`.divg-sym`/`.divg-strike`/`.divg-desc`
  - `.charts-toolbar`/`.toolbar-label`, `.charts-grid`, `.chart-card`
  - `.cal-popover`/`.cal-head`/`.cal-label`/`.cal-grid`/`.cal-dow`/`.cal-cell` (incl. `.tradable` added this run)/`.dim`/`.selected`/`.cal-presets`
  - `.view` + `.active`, `.mono`, `.muted`
- **Keyframes:** shimmer, pulse, fade-up, count-pop (4 total).
- **Media queries:** `@media (max-width:1200px)` (dash-grid→1col, rail static, breadth→2col), `(max-width:900px)` (rolls/charts/breadth→1col), `(max-width:640px)` (header/tab/app-main/kpi/verdict-gauge/cal-popover fixed/roll-cells/divg-item), `@media (prefers-reduced-motion: reduce)` (kill all animations/transitions), `@media print` (hide header/tab-bar/popovers/rail/sparklines/export/toolbar; tables flat black-on-white, positions static).

## How verified
- **Brace/paren validator** (`_csscheck.py`): ALL BALANCED before and after the final edit.
- **Visual review of saved screenshots** (`task-3-shot-dark.png`, `task-3-shot-light.png`, both 1280×2400 from prior session): dark theme (default) and light theme (`body.theme-light`) both render correctly — token swap, KPI cards, badges/pills/status-pill.live, data table with sticky thead + sticky first col + group separators + total-row, instrument blocks, verdict banner/gauge, rolls, conv-tabs, breadth grid, divergence list, takeaways, skeleton, error-card, toast, menu-popover, tab-bar, calendar popover, charts toolbar/grid/cards.
- **Class coverage grep**: every component class in the brief confirmed present; `.cal-cell.tradable` was the only gap and was added.

## Files changed
- `C:\Users\Surajit Pakira\Documents\NFOD\styles.css` (created/committed)

## Commit
- `e321c4d` feat(styles): design-token system + component kit (on branch `redesign/overhaul`, the redesign feature branch — parents are Tasks 1 & 2 commits)

## Self-review notes
- `.cal-cell` base style IS the tradable state (dim is the non-tradable/disabled state); `.cal-cell.tradable` added as explicit selector so later view code can reference it by name.
- `body.theme-dark` is an empty intentional rule (comment documents rationale).
- `::selection` color not themed; not in brief, left out (YAGNI).

## Concerns
- None blocking. Minor: `data-table th:nth-child(3n)` group separators assume tables are laid out in 3-column groups (per brief); if a view uses a 6-col grid the `3n` separator lands mid-group — brief prescribed this, accepted.
- Webkit scrollbar styling is Firefox-neutral no-op; fine.

---

## Fix round 2026-08-01 (post-review)

**Status:** DONE

## Fixes verified (already in working tree, now committed)
1. **Sticky thead** — `.table-scroll` was a 2-axis scroll container (`overflow-x:auto` only), so `position:sticky;top:0` on `.data-table th` never engaged (sticky doesn't work against a non-scrolling parent). Now `overflow-y:auto; max-height:420px` (styles.css ~L214), so the wrapper is a real vertical scroll container and the sticky thead pins. Sticky rule itself at `.data-table th` (L226) confirmed intact.
2. **`.date-chip` border** — was `border-color:var(--border)` with no `border` shorthand, so no border rendered. Now `border:1px solid var(--border)` + `display:inline-block` (styles.css ~L160).

## Specificity nuance (confirmed held)
`.btn` (L131) sets `border:1px solid transparent` at the same specificity (one class) as `.date-chip` (L164). `.date-chip` comes later in source order, so its border declaration wins. Verified empirically: computed style of the harness element (`<span class="date-chip btn btn-sm">`, same class combo as the real `<button class="btn btn-sm date-chip">`) is `borderTopWidth:1px`, `borderTopStyle:solid`, `borderTopColor:rgba(148,163,184,.14)` (= `var(--border)`). Border renders on the real app's date chip.

## RESULT_JSON (from `_t3_verify.py`, system Chrome, headless)
```json
{"date_chip": {"display": "block", "borderTopWidth": "1px", "borderTopStyle": "solid", "borderTopColor": "rgba(148, 163, 184, 0.14)"}, "sticky_before_th_vs_wrap_px": 0.0, "sticky_after_th_vs_wrap_px": 0.0, "wrapper_scroll_occurred": true, "wrapper_scroll_height_vs_client": "836 vs 420"}
```
Interpretation:
- `borderTopWidth:1px`, `borderTopStyle:solid`, color = `var(--border)` — date-chip border renders correctly. **Not** a harness/specificity bug.
- `wrapper_scroll_occurred:true`, scrollHeight 836 > clientHeight 420 — `max-height:420px` applies and the 25-row harness table overflows, so the wrapper actually scrolls.
- `sticky_after_th_vs_wrap_px:0.0` — after scrolling the wrapper 220px, the thead bottom edge sits exactly on the wrapper top: sticky thead engaged and pinned. (Was `position:sticky;top:0` inert before this fix.)
- `date_chip.display:"block"` is correct and NOT a regression: `body` is `display:flex;flex-direction:column`, so the span is a flex item and its `inline-block` is **blockified** to `block` per CSS spec. The value `block` (not `flex`) proves `.date-chip`'s `display:inline-block` is the winning declaration over `.btn`'s `inline-flex`. Border checks are what matter and they pass.

## Stray files cleaned
- Deleted `_t3_probe.html`, `_t3_probe_light.html` from repo ROOT (untracked). Not committed.
- Scratch files in `.superpowers/sdd/2026-08-01-redesign/` (`_t3_verify.html/.py/.png`, `_csscheck.py`, task-3-shot-*.png) left as-is — git-ignored workspace, not part of deliverable.

## Commit
- `7e5bdef` fix(styles): bounded table-scroll for sticky thead, date-chip border (on branch `redesign/overhaul`; only `styles.css`, 7 insertions/2 deletions)

## Fix-round concerns
- None. Both fixes verified in a real browser; no `!important` needed; no harness masking (harness element uses the same `.date-chip .btn .btn-sm` class combo as the real app).

---

## Fix round 2 2026-08-01 (re-review: print clipping)

**Status:** DONE

## Finding
`.table-scroll { overflow-y:auto; max-height:420px }` (fix round 1) makes the wrapper a scroll container. The `@media print` block nullified sticky on th/td (`position:static !important`) but did NOT reset the wrapper's height bound / overflow — a table taller than 420px printed truncated, remaining rows dropped from the hardcopy. Brief requires print tables "flat black-on-white," implying full content.

## Fix
Added inside `@media print` (styles.css, after the th/td static reset, before `.data-table { border-collapse: collapse }`):
```css
.table-scroll { max-height: none; overflow: visible; }
```

## Verification (print-media simulation, Playwright + system Chrome)
New scratch harness `_t3_print_verify.py` (SDD workspace, git-ignored) loads the 25-row harness table, measures wrapper in screen then `emulate_media(media="print")`.

```json
{"screen": {"maxHeight": "420px", "overflowY": "auto", "clientHeight": 420, "scrollHeight": 836},
 "print":  {"maxHeight": "none", "overflowY": "visible", "clientHeight": 839, "scrollHeight": 839, "thPosition": "static"}}
```
Interpretation:
- **Screen**: `max-height:420px` + `overflow-y:auto` still apply → wrapper scrolls, sticky engages (previous fix intact).
- **Print**: `max-height:none`, `overflow-y:visible` → wrapper no longer a scroll/clip container; clientHeight (839) == scrollHeight (839), full table content present, nothing truncated. (839 vs screen 836: black print borders add 1px/row.)
- `thPosition:"static"` in print → sticky still disabled for flat print rendering, as before.
- No clipping: full row count present in print layout.

## Commit
- `12216e8` fix(styles): unclip table-scroll in print (on branch `redesign/overhaul`; only styles.css, 1 insertion)

## Concerns
- None. Both prior fixes (sticky thead, date-chip border) re-verified unaffected — the print rule is additive inside `@media print` only, no screen impact. `.table-scroll` scrollbars gone in print (overflow visible), intended — print uses page flow, not inner scroll.
