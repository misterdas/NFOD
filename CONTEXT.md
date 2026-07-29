# NFOD Project Context

## Overview
**Futures & Options — Participant Wise OI Analysis Dashboard**
A web-based dashboard for analyzing NSE F&O participant-wise Open Interest (OI) data. Tracks FII, DII, Pro, and Client positioning across Index/Stock Futures, Calls, and Puts.

## Tech Stack
- **Frontend**: Vanilla JS, HTML5, CSS3 (glassmorphism design)
- **Charts**: ApexCharts (via CDN)
- **Icons**: FontAwesome 6.5.1
- **Backend Scripts**: Python (CSV data generation, money flow engine)
- **Data**: CSV-based (FDCP_Data.csv), fetched directly by the browser

## Core Files

| File | Purpose |
|------|---------|
| `index.html` | Main dashboard HTML with all views (Gross OI, Money Flow, Charts) |
| `app.js` | Core JS engine — data loading, rendering, event handling, charts |
| `styles.css` | Full UI system with dark/light themes, responsive design |
| `FDCP_Data.csv` | Participant-wise OI data (Client, DII, FII, Pro) |
| `FDCP.py` | Python script to generate/update FDCP_Data.csv |
| `money_flow_engine.py` | Engine for institutional verdict, market breadth analysis |
| `OC.py` | Options chain analysis |
| `fetch_ohlc.py` | Fetches OHLC data for NIFTY candlestick charts |
| `docs/money_flow_data.json` | Generated verdict data (consumed by Money Flow tab) |
| `docs/ohlc_data.json` | OHLC price data for chart candles |

## Key Architecture
- **Instruments tracked**: Index Futures, Index Calls, Index Puts, Stock Futures, Stock Calls, Stock Puts
- **Participants**: Client (Retail), DII, FII, Pro
- **Three views**: Gross OI (main), Money Flow (institutional verdict), Charts (historical trends)
- **Data flow**: CSV → parsed by `parseCSV()` → stored in `rawCSVData[]` → rendered by date filtering
- **Carried positions**: Shows 3-day comparison (Today, 1D Ago, 2D Ago)
- **Front-loaded**: All data loaded on init, no API calls beyond static file fetches

## Current State (as of last update)
- Working features: Date navigation, KPI cards, 6 instrument tables, right-hand summary, dark/light themes, hamburger menu
- Money Flow tab: Executive verdict, FII/Pro/DII stance, index rolls, multi-day conviction matrix (NIFTY/BANKNIFTY), stock breadth (4 tables)
- Charts tab: 4 charts (FII/DII/Pro/Client) with optional NIFTY candlestick overlay
- CSS architecture: glassmorphism design with dark/light themes and responsive breakpoints (1200px, 992px, 768px, 480px)

## Money Flow Tab Details
### Panel 1: Executive Market Verdict
- Bias badge (bullish/bearish/neutral), Smart Money Score, action description
- Retail Trap Alarm (call-trap red / put-trap green) when retail is caught on wrong side

### Panel 2: Participant Positioning (FII, Pro, DII, Retail)
- FII: Call options stance, Put options stance, Futures net shift
- Pro: Overall stance (bullish/bearish/neutral)
- Retail: Client net calls (trap risk indicator)
- DII: Call shift, Put shift, Futures net shift
- Info footer shows date, FII futures carried, and raw scores for all participants
- All actions displayed using CSS `stance-badge` classes (no inline emojis)

### Panel 3: Index Rolls, Magnet Strike & Expiry Targets
- Per-index cards with resistance/support rolls (bullish/bearish accent bars via ::before pseudo-elements)
- Magnet strike and expected expiry range
- Traps & squeezes (synthetic premium/discount, call writer squeeze, put writer trap)
- Max pain, PCR OI/DOI displayed

### Panel 4: Multi-Day Strike Conviction Matrix
- NIFTY and BANKNIFTY tabs (clickable, data loaded from `conviction_trends`)
- 5-day OI trend delta for calls and puts
- Conviction tags: HARD RESISTANCE, CE BUILDING, CE UNWINDING, SOLID FLOOR, PE BUILDING, PE UNWINDING, STABLE
- CSS classes for color-coded conviction indicators (no inline styles)

### Panel 5: Stock Market Breadth
- 4-column grid on large screens (>=1200px), stacks on smaller:
  1. Fresh Call Writing (operators capping upside)
  2. Fresh Put Writing (operators defending floor)
  3. Call Unwinding (short squeeze risk)
  4. Put Unwinding (floor breakdown risk)
- Top 10 stocks per category with LTP, top strike, and OI delta

## Scoring Methodology
- **FII weight = 1.00** (largest, most informational)
- **Pro weight = 0.60** (prop desks/arbitrageurs)
- **DII weight = 0.40** (mutual funds/insurers, slower-moving)
- **Client/Retail**: Never scored directly, used as contrarian overlay only
- Per-participant scoring rubric (each +-25 pts):
  - Futures change: +25 (>threshold), -25 (<-threshold)
  - Call short change: +25 (covering=bullish), -25 (writing=bearish)
  - Put short change: +25 (writing=bullish floor), -25 (unwinding=bearish)
- Composite clipped to [-100, +100]
- Retail trap adjustment: +-15 when retail heavily positioned against FII

## CSS Architecture
- Global variables for colors, shadows, radius, typography
- Dark/light themes via body.theme-dark toggle
- New money flow CSS classes (in styles.css, "Refactored Inline-Style Classes" section):
  - `.participant-section-label` (`.fii`/`.pro`/`.dii`/`.retail` variants)
  - `.participant-data-row` (`.label`, `.value` children)
  - `.stance-badge` (`.bullish`/`.bearish`/`.neutral`/`.caution` variants)
  - `.conviction-tag` (7 conviction type variants)
  - `.roll-card` (`.bullish`/`.bearish` accent bar via `::before`)
  - `.info-footer`, `.magnet-info-bar`, `.retail-trap-alarm`
  - `.conviction-tab`, `.skeleton-loader`, `.retry-btn`
  - `.traps-container`, `.trap-badge`, `.breadth-heading-unwind-*`
- No inline `style="..."` attributes in rendered money flow panels
- Responsive: breadth grid switches 4col -> 2col -> 1col

## Notes
- Dark theme is default
- Indian number formatting used throughout
- No build system — pure static files
- Mobile-responsive with touch optimizations
- Tables have column group separators (2px) between all groups: PARTICIPANT | LONGS | SHORTS | NET TODAY | TODAY | 1D AGO | 2D AGO, excluding the total row
- Total row shows `-` for carried positions (TODAY, 1D AGO, 2D AGO)
