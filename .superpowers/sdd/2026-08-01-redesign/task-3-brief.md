### Task 3: styles.css — design token system

**Files:**
- Create: `styles.css`

**Interfaces:**
- Produces: CSS custom-property tokens consumed by all later tasks. Every component class below is used by views.

- [ ] **Step 1: Write token layer (dark default + light override)**

```css
/* ── Design tokens ─────────────────────────────────────────── */
:root {
  --font-sans: "Inter", -apple-system, "Segoe UI", Roboto, sans-serif;
  --font-mono: "JetBrains Mono", Menlo, Consolas, monospace;
  --space-1: 4px; --space-2: 8px; --space-3: 12px; --space-4: 16px;
  --space-5: 24px; --space-6: 32px; --space-7: 48px;
  --radius-sm: 6px; --radius-md: 8px; --radius-lg: 12px; --radius-xl: 16px;
  --shadow-sm: 0 1px 2px rgba(0,0,0,.3);
  --shadow-md: 0 4px 12px rgba(0,0,0,.25);
  --shadow-lg: 0 12px 32px -8px rgba(0,0,0,.5);
  --ease-out: cubic-bezier(.16,1,.3,1);
  --dur-fast: 150ms; --dur-norm: 250ms; --dur-slow: 400ms;
  /* Dark palette (default) */
  --surface-1: #0a0c10; --surface-2: #11141b; --surface-3: #1a1f29;
  --border: rgba(148,163,184,.14); --border-strong: rgba(99,102,241,.35);
  --text-1: #eef2f7; --text-2: #a7b0c2; --text-3: #64718a;
  --up: #34d399; --up-bg: rgba(52,211,153,.1);
  --down: #f87171; --down-bg: rgba(248,113,113,.1);
  --warn: #fbbf24; --warn-bg: rgba(251,191,36,.1);
  --info: #38bdf8; --info-bg: rgba(56,189,248,.1);
  --accent: #6366f1; --accent-2: #a78bfa;
  --accent-grad: linear-gradient(135deg, #6366f1, #a78bfa);
  --header-bg: rgba(10,12,16,.85);
}
body.theme-light {
  --surface-1: #f8fafc; --surface-2: #ffffff; --surface-3: #eef2f7;
  --border: rgba(15,23,42,.1); --border-strong: rgba(99,102,241,.3);
  --text-1: #0f172a; --text-2: #475569; --text-3: #94a3b8;
  --up: #059669; --up-bg: rgba(5,150,105,.08);
  --down: #dc2626; --down-bg: rgba(220,38,38,.08);
  --warn: #d97706; --warn-bg: rgba(217,119,6,.08);
  --info: #0284c7; --info-bg: rgba(2,132,199,.08);
  --header-bg: rgba(255,255,255,.9);
  --shadow-sm: 0 1px 2px rgba(15,23,42,.06);
  --shadow-md: 0 4px 12px rgba(15,23,42,.08);
  --shadow-lg: 0 12px 32px -8px rgba(15,23,42,.15);
}
```

- [ ] **Step 2: Write base + component classes**

Base: reset, `body { background: var(--surface-1); color: var(--text-1); font: 13px/1.5 var(--font-sans); }`, `.font-mono { font-family: var(--font-mono); font-variant-numeric: tabular-nums; }`.

Components (class → key properties):
- `.kpi-card` — surface-2, radius-lg, shadow-sm, border, padding space-4.
- `.kpi-value` — font-mono, 24px/800. `.kpi-value.pos-up { color: var(--up) }`, `.pos-down { color: var(--down) }`.
- `.instrument-block` — surface-2, radius-lg, border, overflow hidden.
- `.block-header` — surface-3, 10px uppercase letter-spacing, bold.
- `.data-table` — full-width, `th { background: var(--surface-3); font-size: 10px; text-transform: uppercase; }`, `td { font-family: var(--font-mono); font-size: 11.5px; }`, sticky thead (`position: sticky; top: 0`), row hover `background: var(--surface-3)`, group-column separators via `td:nth-child(3n)` borders.
- `.total-row` — surface-3 bg, bold.
- `.sticky-col-first` — sticky left column for participant names.
- `.badge`, `.badge.bullish/.bearish/.neutral/.caution` — pill, 10px bold, bg tint.
- `.pill`, `.pill-green/.pill-red/.pill-yellow/.pill-purple` — small stat chips.
- `.btn` (primary/secondary/ghost/icon), `.btn-sm` — 12px semibold, radius-sm, accent-grad for primary.
- `.select` — surface-2, border, radius-sm.
- `.skeleton` — shimmer block, `background: linear-gradient(90deg, var(--surface-3) 25%, var(--surface-2) 50%, var(--surface-3) 75%); animation: shimmer 1.5s infinite`.
- `.error-card` — down-bg tint, border, padding, radius-md, with `.retry-btn`.
- `.tab-bar`, `.tab-btn`, `.tab-btn.active` — underline pill active state.
- `.date-chip`, `.sparkline` — inline-block.
- `.status-pill`, `.status-pill.live { color: var(--up); animation: pulse }` (pulse keyframe opacity).
- `.verdict-gauge` — score display, accent-grad text on big score.
- `.toast` — fixed bottom, surface-2, shadow-lg, for export/download confirmations.
- Theme toggle button, hamburger dropdown (`.menu-popover`).

Add `@keyframes shimmer`, `pulse`, `fade-up`, `count-pop`. Add `@media (prefers-reduced-motion: reduce)` disabling all animations/transitions. Add `@media print` hiding header nav, rendering tables as flat black-on-white.

- [ ] **Step 3: Verify**

Load a scratch HTML referencing `styles.css` and eyeball: token swap via `body.theme-light`, skeleton shimmer, badge tints, sticky table header. Fix any broken selectors.

- [ ] **Step 4: Commit**

```bash
git add styles.css
git commit -m "feat(styles): design-token system + component kit"
```

---

