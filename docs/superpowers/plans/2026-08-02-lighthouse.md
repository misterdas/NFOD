# Lighthouse Score Improvement Plan (2026-08-02)

## Goal
Raise Lighthouse category scores (desktop + mobile) **without redesigning or visibly changing the UI**. Only zero-visual or near-zero-visual changes (semantics, loading strategy, dead code, one gray token, minimal label-size bumps for the mobile legibility audit).

## Baseline (audited 2026-08-02, served at http://localhost:8000)

| Category | Desktop | Mobile |
|---|---|---|
| Performance | 66 | 75 |
| Accessibility | 94 | 94 |
| Best Practices | 100 | 96 |
| SEO | 90 | 90 |

### Weighted failures
- **SEO both**: `meta-description` missing.
- **A11y both**: `color-contrast` — 20 items, all from `--text-3` (#64718a dark) on surfaces 1/2/3 (3.75:1 vs 4.5:1 needed): `.kpi-header`, `.kpi-sub`, `.data-table th`, `.app-footer`.
- **A11y desktop**: `td-has-header` — right-rail instrument tables in gross view have a label column rendered as `<td>`.
- **BP mobile**: `font-size` — 15.52% legible; 10–11.5px text in `.kpi-header`, `.kpi-sub`, `.data-table th`, `.data-table.compact td`, `.block-header`, `.app-footer`, `.rail-title`, `.data-table td`.
- **Perf desktop**: TBT 310ms (0.56), CLS 0.396 (0.25), SI 1.4s (0.87).
- **Perf mobile**: CLS 0.919 (0.03) — async Key Takeaways append pushes content down; web-font swap shifts table cells. FCP/LCP 1.8s driven by render-blocking resources (~950ms est savings).

## Fixes

1. **SEO — meta description** (non-visual)
   Add `<meta name="description">` to `index.html` head.

2. **Perf — unblock parsing** (non-visual, ~600ms FCP)
   Add `defer` to all 8 `<script>` tags in `index.html`. `defer` preserves document order, so the load-order contract (`utils → data → sparkline → calendar → gross → verdict → charts → app`) is intact; all run before `DOMContentLoaded` exactly as today.

3. **Perf — non-blocking Google Fonts CSS** (non-visual, ~885ms FCP)
   Load `css2` stylesheet with `media="print" onload="this.media='all'"`; keep preconnect to `fonts.googleapis.com` + add `fonts.gstatic.com`. `display=swap` already in URL → no FOUT policy change.

4. **Perf/CLS — reserve space for async takeaways** (non-visual)
   `.takeaways` in gross view is appended async via `insertAdjacentHTML` after the money-flow JSON resolves; give it a min-height so the append doesn't shift the page (mobile CLS 0.919).

5. **Perf/CLS — preload font woff2 files** (non-visual)
   Extract the two woff2 URLs from the css2 response for Chromium and add `<link rel="preload" as="font" type="font/woff2" crossorigin>` — shrinks the swap window that shifts table cells.

6. **A11y — contrast** (one gray token, near-invisible)
   - Dark: `--text-3: #64718a → #7988a3` (passes 4.61 vs surface-3, 5.14 vs surface-2).
   - Light: `--text-3: #94a3b8 → #5f6b7d` (passes 4.81 vs surface-3, 5.40 vs white).

7. **A11y — td-has-header** (zero visual)
   Right-rail instrument tables in `views/gross.js`: render first column as `<th scope="row">`; style `th` identical to the current `td` (weight/color/alignment) so rendering is unchanged.

8. **BP mobile — legible font sizes** (minimal visual delta: 10–11.5px → 12px)
   `.kpi-header`, `.kpi-sub`, `.data-table th`, `.data-table.compact td`, `.block-header`, `.app-footer`, `.rail-title`, `.data-table td` all to 12px minimum. **This is the only visible change** (labels ~1–2px larger); required for the mobile legibility audit.

9. **Perf — dead CSS** (non-visual)
   Remove `.tab-btn`/`.tab-bar` rules — nav moved to the menu popover; no live consumer. Skip blanket unused-CSS trimming: charts/verdict view CSS looks "unused" because Lighthouse only renders the gross view. Skip minification (would need a build step for 5 KiB).

## Not site bugs (environment artifacts of `python -m http.server`)
- `uses-long-cache-ttl` (no Cache-Control), `uses-text-compression` (no gzip) — GitHub Pages sends both. Confirm via a Pages-URL run in verification.

## Verification
- Re-run `lighthouse` desktop + mobile against localhost:8000; compare category scores to baseline.
- Re-run once against the deployed GitHub Pages URL to confirm cache/compression audits pass.
