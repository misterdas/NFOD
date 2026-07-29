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
- Money Flow tab: Executive verdict, FII/Pro stance, index rolls, multi-day conviction matrix, stock breadth
- Charts tab: 4 charts (FII/DII/Pro/Client) with optional NIFTY candlestick overlay
- All 3 files (index.html, app.js, styles.css) have uncommitted changes

## Notes
- Dark theme is default
- Indian number formatting used throughout
- No build system — pure static files
- Mobile-responsive with touch optimizations
- Tables have column group separators (2px) between all groups: PARTICIPANT | LONGS | SHORTS | NET TODAY | TODAY | 1D AGO | 2D AGO, excluding the total row
- Total row shows `-` for carried positions (TODAY, 1D AGO, 2D AGO)
