# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**NFOD** (NSE F&O Data Pipeline) — daily pipeline that fetches NSE participant-wise OI data, option chains, and NIFTY OHLC, runs an institutional verdict engine, publishes a static dashboard (GitHub Pages) and sends Telegram summaries.

**Stack**: Python 3.14 (pandas, numpy, requests, nsefetch, yfinance) + Vanilla JS/HTML/CSS (no build system). ApexCharts via CDN.

**Deploy**: GitHub Actions (`.github/workflows/data_update_and_deploy.yml`) runs `python main.py all` daily at 14:30 UTC (20:00 IST, Mon–Fri), commits data, deploys to GitHub Pages. Telegram creds via repo secrets `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.

---

## Commands

```bash
# Full pipeline (all 5 phases sequentially)
python main.py all

# Individual phases
python main.py fdcp       # Fetch FDCP participant OI CSV (60-day window → FDCP_Data.csv)
python main.py oc         # Fetch option chain for all F&O symbols (parallel workers)
python main.py ohlc       # Fetch NIFTY OHLC via yfinance (75-day window)
python main.py engine     # Run verdict engine → docs/money_flow_data.json
python main.py engine --dry-run  # Diagnostics: print scoring, NO output file written
python main.py telegram   # Send Gross OI page to Telegram (mirrors dashboard)

# Dependencies
pip install -r requirements.txt   # pandas, requests, nsefetch, yfinance
```

**Order matters**: `engine` requires `nse_data.json` (from `oc`). `telegram` reads `FDCP_Data.csv` + `money_flow_data.json`.

---

## Architecture

### Core Files

| File | Role |
|------|------|
| `main.py` | CLI entry — maps commands to `nse_toolkit.*` functions |
| `nse_toolkit/config.py` | All paths, thresholds, weights, symbol lists, utilities (`clean_val`, `sort_dates_chronologically`) |
| `nse_toolkit/fetcher.py` | 3 fetchers + `update_embedded_csv()` (injects CSV into app.js) |
| `nse_toolkit/engine.py` | Verdict engine: participant scoring, index rolls, stock breadth, conviction, flow divergence |
| `nse_toolkit/telegram.py` | Telegram sender — replicates dashboard Gross OI math in Python |
| `index.html` | Static dashboard (3 views: Gross OI, Money Flow, Charts) |
| `app.js` | Frontend — embeds FDCP CSV, fetches JSON, renders everything |
| `FDCP_Data.csv` | Raw participant OI (Client/DII/FII/Pro × 6 instruments × dates) |
| `docs/money_flow_data.json` | Engine output — consumed by Money Flow tab |
| `docs/ohlc_data.json` | NIFTY OHLC candles for charts |
| `docs/nse_data.json` | Current option-chain snapshot (all stocks) |
| `docs/oc_history/YYYY-MM-DD.json` | Daily OC archives (multi-day conviction, 30-day retention) |

### Data Flow

```
NSE Archives → FDCP_Data.csv (60 days)
     │                     │
     │              update_embedded_csv() → app.js _EMBEDDED_CSV
     ↓
NSE Option Chain API → docs/nse_data.json + docs/oc_history/<date>.json
     ↓
yfinance → docs/ohlc_data.json
     ↓
engine.py → docs/money_flow_data.json
     ↓
Telegram bot (env creds)          GitHub Pages (index.html + app.js + docs/)
```

### Dashboard Views (app.js)

1. **Gross OI** (`view-participant-gross`): 6 instrument tables + 4 KPI cards + right-hand "bought/sold today" summary + Key Takeaways. Data from embedded `_EMBEDDED_CSV`.
2. **Money Flow** (`view-money-flow`): executive verdict banner, index rolls/magnet strike/traps, FII/Pro/DII stance, multi-day conviction matrix, flow divergence, 4-column stock breadth. Data from `docs/money_flow_data.json`.
3. **Charts** (`view-charts`): ApexCharts candlestick+line overlays, from embedded CSV + `docs/ohlc_data.json`.

---

## Data Formats (for parsing/writing)

### FDCP_Data.csv columns
```
Client Type, Future Index Long, Future Index Short, Future Stock Long, Future Stock Short,
Option Index Call Long, Option Index Put Long, Option Index Call Short, Option Index Put Short,
Option Stock Call Long, Option Stock Put Long, Option Stock Call Short, Option Stock Put Short,
Total Long Contracts, Total Short Contracts, Date (DD-MM-YYYY)
```
- Header has **trailing spaces** on some columns (`Future Stock Short   `) — code strips (`df.columns.str.strip()` in Python; `.trim()` in JS parseCSV).
- Participants: `Client`, `DII`, `FII`, `Pro` (Client = retail, contrarian only).
- Net change = today − prev day per column. "Net Today" column = longΔ − shortΔ.

### docs/money_flow_data.json — top-level keys
```
timestamp (ISO UTC)
executive_summary: {bias_label, smart_money_score, action_desc, score_breakdown}
participant_summary: {date, prev_date, smart_money_score, bias_label,
                      retail_trap_alarm, trap_adjustment, retail_confirmation_message,
                      retail_confirmation_score, fii_dii_modifier, iv_modifier_applied,
                      weighted_clipped_before_adjustments,
                      <prefix>_fut_net_change, _fut_long_change, _fut_short_change,
                      _ce_long_change, _ce_short_change, _ce_net_short_change,
                      _pe_long_change, _pe_short_change, _pe_net_short_change,
                      _raw_score, _stk_fut_net_change, _stk_fut_long_change,
                      _stk_fut_short_change, _stk_ce_net_change, _stk_pe_net_change
                      where prefix ∈ {fii, pro, dii},
                      client_ce_net_buy, client_pe_net_buy, client_*_change (same legs),
                      fii_fut_net_carried, pro_fut_net_carried, dii_fut_net_carried,
                      weights {fii, pro, dii, client}}
index_rolls: {NIFTY, BANKNIFTY, FINNIFTY, MIDCPNIFTY: {
                ltp, expiry (DD-MMM-YYYY), max_pain, magnet_strike, expiry_range,
                pcr_oi, pcr_doi, divergence,
                resistance_wall, fresh_resistance, support_wall, fresh_support,
                resistance_roll, resistance_roll_type (BULLISH/BEARISH/NEUTRAL),
                resistance_roll_desc, support_roll, support_roll_type, support_roll_desc,
                traps_and_squeezes: [{type, strike, badge, desc}]}}
stock_breadth: {call_writing_bearish, put_writing_bullish, call_unwinding_bullish,
                put_unwinding_bearish: [{symbol, ltp, net_ce_doi, net_pe_doi,
                top_ce_write_strike, top_ce_write_doi, top_pe_write_strike, top_pe_write_doi,
                top_ce_unwind_strike, top_ce_unwind_doi, top_pe_unwind_strike, top_pe_unwind_doi,
                alignment (ALIGNED/OPPOSED/NEUTRAL)}],
                counts {call_writing, put_writing, call_unwinding, put_unwinding}}
conviction_trends: {NIFTY, BANKNIFTY: {dates: [YYYY-MM-DD], strikes: [{
                strike, ce_oi_history[], pe_oi_history[], today_ce_doi, today_pe_doi,
                ce_trend_delta, pe_trend_delta, ce_conviction, pe_conviction,
                ce_alignment, pe_alignment, ce_flow_attr, pe_flow_attr}]}}
flow_divergence: [{symbol, strike, type (CONFLICT_ZONE/BULLISH_DIVERGENCE/
                BEARISH_DIVERGENCE/RESISTANCE_BUILDING/FLOOR_WEAKENING),
                signal, desc}]  (max 8)
stock_count
```

---

## Scoring Methodology (engine.py)

### Weighted composite
```
fii_raw_score × 1.00 + pro_raw_score × 0.60 + dii_raw_score × 0.40
→ clipped to [-150, +150]
→ + trap_adjustment ±15
→ + retail_confirmation_score ±5
→ + fii_dii_modifier (alignment ±10, opposite −10)
→ + iv_modifier (±10)
→ final smart_money_score (clipped ±150)
```

### Per-participant raw score (max ±25/leg, proportional)
Base ±15 for crossing threshold + up to ±10 proportional beyond it (ratio capped at 1.0).

| Leg | Bullish (+15..25) | Bearish (−15..25) |
|-----|-------------------|-------------------|
| Futures (`fut_chg`) | > +threshold (buying) | < −threshold (selling) |
| Call net-short (`ce_net_short_chg`) | < −threshold (covering = bullish) | > +threshold (writing = bearish) |
| Put net-short (`pe_net_short_chg`) | > +threshold (writing floor = bullish) | < −threshold (unwinding = bearish) |

`ce_net_short_chg = ce_short_chg − ce_long_chg`; `pe_net_short_chg = pe_short_chg − pe_long_chg`. Long & short legs always netted first (adding both long+short doesn't register as directional).

### Bias labels (by score)
| Score | Label |
|-------|-------|
| ≥ 40 | HIGH CONFIDENCE BULLISH |
| ≥ 15 | MODERATE BULLISH |
| ≤ −40 | HIGH CONFIDENCE BEARISH |
| ≤ −15 | MODERATE BEARISH |
| else | NEUTRAL / SIDEWAYS |

### Retail (Client) contrarian overlay
- **Call trap** (−15): client buys >25k calls while FII writes calls (>10k net-short).
- **Put trap** (+15): client buys >25k puts while FII writes puts.
- **Confirmation** (±5): client *reduces* positions while FII does same direction.

---

## Key Thresholds (config.py)

| Constant | Value | Meaning |
|----------|-------|---------|
| `FII_FUT_THRESHOLD` | 5000 | FII futures leg threshold |
| `FII_OPT_THRESHOLD` | 10000 | FII options leg threshold |
| `PRO_FUT_THRESHOLD` | 3000 | Pro futures leg |
| `PRO_OPT_THRESHOLD` | 6000 | Pro options leg |
| `DII_FUT_THRESHOLD` | 2000 | DII futures leg |
| `DII_OPT_THRESHOLD` | 4000 | DII options leg |
| `RETAIL_TRAP_THRESHOLD` | 25000 | Client net buy trigger |
| `SCORE_CLIP` | 150 | Composite clip bound |
| `IV_MOD_MAX` / `IV_MOD_BOOST` | 10 / 5 | IV modifier caps |
| `IV_HIGH_THRESH` / `IV_LOW_THRESH` | 25 / 12 | IV bounds |
| `FDCP_DAYS` | 60 | FDCP lookback |
| `OHLC_DAYS` | 75 | OHLC lookback |
| `OC_WORKERS` / `OC_DELAY` | 3 / 0.05s | OC fetch pacing |
| `OC_RETRIES` | 3 | Per-symbol retries |
| `OC_BLOCK_COOLDOWN` | 5s | NSE anti-bot pause |
| `OC_BREAKER_BLOCK/FAILURE_THRESHOLD` | 50 | nsefetch circuit breaker |

### Weights
`FII_WEIGHT=1.00`, `PRO_WEIGHT=0.60`, `DII_WEIGHT=0.40`, Client=0.0 (never scored).

---

## Instrument/Participant Mappings (shared across app.js, telegram.py, engine.py)

| Instrument ID | title | longCol | shortCol |
|---|---|---|---|
| index-futures | Index Futures | Future Index Long | Future Index Short |
| index-calls | Index Calls | Option Index Call Long | Option Index Call Short |
| index-puts | Index Puts | Option Index Put Long | Option Index Put Short |
| stock-futures | Stock Futures | Future Stock Long | Future Stock Short |
| stock-calls | Stock Calls | Option Stock Call Long | Option Stock Call Short |
| stock-puts | Stock Puts | Option Stock Put Long | Option Stock Put Short |

Participants: `Client`, `DII`, `FII`, `Pro`.

**Important**: `app.js` INSTRUMENTS and `telegram.py` INSTRUMENTS are **duplicated definitions** — changing one requires updating both.

---

## Engine internals (engine.py)

- **`detect_index_rolls`**: works on `INDICES` (NIFTY, BANKNIFTY, FINNIFTY, MIDCPNIFTY). Resistance/support rolls from fresh vs unwind strike (CE/PE ΔOI). Max pain via brute-force loss minimisation. Magnet = `0.5·max_pain + 0.25·res_wall + 0.25·sup_wall`, rounded to strike step. Traps: synthetic premium (CE−PE parity > ±20pts), call-writer squeeze, put-writer trap. DTE-weighting applied to ΔOI.
- **`scan_stock_breadth`**: top-10 lists per category. Threshold = `max(500, net_oi * 0.05)` per stock. Alignment compares stock ΔOI direction to FII call/put stance.
- **`build_multiday_conviction`**: reads last 5 `oc_history/*.json` files. Trend delta = `last − first` OI across those files. Conviction thresholds scaled per index (`scale = avg_ce_oi / NIFTY_avg_ce_oi`): hard_res=25000·scale, building=2500·scale, unwind=1500·scale. Top 15 strikes near latest LTP.
- **`detect_flow_divergence`**: per-index scaled thresholds (NIFTY baseline): conflict=5000·scale, unwind=5000·scale, resistance=8000·scale, floor=5000·scale. Returns max 8.
- **`compute_iv_modifier`**: mean ATM (±2%) CE/PE IV across INDICES. `avg_iv > 25` → `−(avg_iv−25)·0.5` (max 10); `avg_iv < 12` → `+(12−avg_iv)·1.0` (max 5).

---

## Frontend logic (app.js)

- **Embedded CSV**: `var _EMBEDDED_CSV="<csv>"`; rebuilt by `update_embedded_csv()` in fetcher.py using exact boundaries `var _EMBEDDED_CSV="` … `";let rawCSVData=`. **Do not reformat this string** — the regenerator matches it byte-for-byte (comma-first, `\r\n` delimiters).
- **`_fetchWithCacheBust`**: appends `?d=<floor(Date.now()/864e5)>` (day-bucket) to all static JSON fetches — avoids caching stale data while allowing CDN cache reuse within a day.
- **KPI bias** (dashboard, `updateKPIs`): `FII futuresΔ + Pro call net + Pro put net`, where Pro put net is `pro_puts = pe_shortΔ − pe_longΔ` (sign flipped so put-writing counts bullish). Thresholds ±20k → BULLISH/BEARISH/NEUTRAL.
- **KPI bias** (Telegram, `build_kpi_message`): must match dashboard exactly. Recent fix: added Pro put leg — when changing one, keep both in sync.
- **Takeaways**: `renderGrossOITakeaways` (JS) and `build_takeaways_message` (Python) duplicate logic — expiry math (`_days_to_monthly_expiry`) replicated exactly (uses **last-Tuesday proxy** `getDay()-2`, not last Thursday — matches dashboard even if "wrong").
- **Charts**: ApexCharts candlestick (NIFTY OHLC) + line overlays (Call net-short / Put net-short holdings per participant). Candlestick chart shows only dates where OHLC exists.
- Indian number formatting (`formatIndianNum` / `_inr`): en-IN locale thousands separators, `-` for null. Signs: green = positive-ish, red = negative (semantics vary per column — read the specific renderer).

---

## Gotchas & Cross-file Consistency

1. **CSV trailing-space columns**: always `.strip()` header names before lookup (both Python `_load_rows` and JS `parseCSV`).
2. **app.js ↔ telegram.py parity**: instrument lists, KPI math, takeaways, expiry logic are duplicated. Verify both change together.
3. **OC anti-bot**: nsefetch session blocks handled via shared threading events + global cooldown + `bootstrap_session(force=True)`. Don't lower circuit-breaker thresholds (burst of 403s would hard-open the breaker).
4. **`main.py all` ordering**: fdcp → oc → ohlc → engine → telegram. OC can take a while (200+ symbols, parallel, paced).
5. **Date formats**: CSV uses `DD-MM-YYYY`; oc_history files `YYYY-MM-DD`; OHLC `YYYY-MM-DD`; expiry `DD-MMM-YYYY`.
6. **JSON cleanliness**: `clean_val()` strips numpy/pandas types before `json.dump` — any new engine field must flow through it.
7. **GitHub Actions**: Python 3.14, cache pip, commit+push with 3 retries (rebase on conflict), deploy-pages only after update-data. Pages serves repo root.
