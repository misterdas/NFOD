"""
Shared configuration, thresholds, paths, and utility functions for the NFOD toolkit.
"""

import os
import numpy as np

# ── Paths ──────────────────────────────────────────────────────────────────
OUTPUT_DIR = "docs"
FDCP_FILE = "FDCP_Data.csv"
NSE_DATA_FILE = os.path.join(OUTPUT_DIR, "nse_data.json")
HISTORY_DIR = os.path.join(OUTPUT_DIR, "oc_history")
OHLC_FILE = os.path.join(OUTPUT_DIR, "ohlc_data.json")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "money_flow_data.json")

# ── FDCP fetch defaults ────────────────────────────────────────────────────
FDCP_DAYS = 60         # look-back window for FDCP CSV fetch
FDCP_WORKERS = 5       # parallel workers for FDCP date fetching

# ── OC fetch defaults ──────────────────────────────────────────────────────
OC_WORKERS = 3        # parallel workers for option chain symbol fetching
OC_DELAY = 0.05        # inter-request backoff (seconds)
OC_RETRIES = 3         # max retries per symbol
OC_BLOCK_COOLDOWN = 5  # global pause (seconds) after an NSE anti-bot block before retrying
# ── OHLC fetch defaults ────────────────────────────────────────────────────
OHLC_DAYS = 75

# ── Participant weights (FII > Pro > DII > Client) ─────────────────────────
FII_WEIGHT = 1.00
PRO_WEIGHT = 0.60
DII_WEIGHT = 0.40
# Client (retail) weight is 0.0 — never scored directly, used as contrarian overlay only.

# ── Score thresholds ────────────────────────────────────────────────────────
FII_FUT_THRESHOLD = 5000
FII_OPT_THRESHOLD = 10000
PRO_FUT_THRESHOLD = 3000
PRO_OPT_THRESHOLD = 6000
DII_FUT_THRESHOLD = 2000
DII_OPT_THRESHOLD = 4000
RETAIL_TRAP_THRESHOLD = 25000
SCORE_CLIP = 150

# ── IV modifier bounds ─────────────────────────────────────────────────────
IV_MOD_MAX = 10
IV_MOD_BOOST = 5
IV_HIGH_THRESH = 25
IV_LOW_THRESH = 12

# ── Indices ─────────────────────────────────────────────────────────────────
ALL_FNO_STOCKS: list[str] = [
    "NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "NIFTYNXT50",
    "360ONE", "ABB", "ABCAPITAL", "ADANIENSOL", "ADANIENT", "ADANIGREEN", "ADANIPORTS", "ADANIPOWER",
    "ALKEM", "AMBER", "AMBUJACEM", "ANGELONE", "APLAPOLLO", "APOLLOHOSP", "ASHOKLEY", "ASIANPAINT",
    "ASTRAL", "AUBANK", "AUROPHARMA", "AXISBANK", "BAJAJ-AUTO", "BAJAJFINSV", "BAJAJHLDNG",
    "BAJFINANCE", "BANDHANBNK", "BANKBARODA", "BANKINDIA", "BDL", "BEL", "BHARATFORG", "BHARTIARTL",
    "BHEL", "BIOCON", "BLUESTARCO", "BOSCHLTD", "BPCL", "BRITANNIA", "BSE", "CAMS", "CANBK",
    "CDSL", "CGPOWER", "CHOLAFIN", "CIPLA", "COALINDIA", "COCHINSHIP", "COFORGE", "COLPAL",
    "CONCOR", "CROMPTON", "CUMMINSIND", "DABUR", "DALBHARAT", "DELHIVERY", "DIVISLAB", "DIXON",
    "DLF", "DMART", "DRREDDY", "EICHERMOT", "ETERNAL", "FEDERALBNK", "FORCEMOT",
    "FORTIS", "GAIL", "GLENMARK", "GMRAIRPORT", "GODFRYPHLP", "GODREJCP", "GODREJPROP", "GRASIM",
    "GVT&D", "HAL", "HAVELLS", "HCLTECH", "HDFCAMC", "HDFCBANK", "HDFCLIFE", "HEROMOTOCO",
    "HINDALCO", "HINDPETRO", "HINDUNILVR", "HINDZINC", "HYUNDAI", "ICICIBANK", "ICICIGI",
    "ICICIPRULI", "IDEA", "IDFCFIRSTB", "IEX", "INDHOTEL", "INDIANB", "INDIGO", "INDUSINDBK",
    "INDUSTOWER", "INFY", "INOXWIND", "IOC", "IREDA", "IRFC", "ITC", "JINDALSTEL", "JIOFIN", "JSWENERGY",
    "JSWSTEEL", "JUBLFOOD", "KALYANKJIL", "KAYNES", "KEI", "KFINTECH", "KOTAKBANK", "KPITTECH",
    "LAURUSLABS", "LICHSGFIN", "LICI", "LODHA", "LT", "LTF", "LTM", "LUPIN", "MANAPPURAM", "M&M", "MANKIND",
    "MARICO", "MARUTI", "MAXHEALTH", "MAZDOCK", "MCX", "MFSL", "MOTHERSON", "MOTILALOFS",
    "MPHASIS", "MUTHOOTFIN", "NAM-INDIA", "NATIONALUM", "NAUKRI", "NBCC", "NESTLEIND", "NHPC",
    "NMDC", "NTPC", "NYKAA", "OBEROIRLTY", "OFSS", "OIL", "ONGC", "PAGEIND",
    "PATANJALI", "PAYTM", "PERSISTENT", "PETRONET", "PFC", "PGEL", "PHOENIXLTD", "PIDILITIND",
    "PIIND", "PNB", "PNBHOUSING", "POLICYBZR", "POLYCAB", "POWERGRID", "POWERINDIA",
    "PREMIERENE", "PRESTIGE", "RADICO", "RBLBANK", "RECLTD", "RELIANCE", "RVNL", "SAIL",
    "SBICARD", "SBILIFE", "SBIN", "SHREECEM", "SHRIRAMFIN", "SIEMENS", "SOLARINDS", "SONACOMS", "SRF",
    "SUNPHARMA", "SUPREMEIND", "SUZLON", "SWIGGY", "TATACONSUM", "TATAELXSI", "TATAPOWER", "TATASTEEL", "TCS", "TECHM", "TIINDIA", "TITAN",
    "TMPV", "TORNTPHARM", "TRENT", "TVSMOTOR", "ULTRACEMCO", "UNIONBANK", "UNITDSPR",
    "UNOMINDA", "UPL", "VBL", "VEDL", "VMM", "VOLTAS", "WAAREEENER", "WIPRO", "YESBANK",
    "ZYDUSLIFE",
]

# Match old engine: analysis (rolls, IV, divergence) uses 4 core indices
INDICES: list[str] = ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"]
# Fetcher includes NIFTYNXT50 as an index type (same as old OC.py)
FETCH_INDICES: list[str] = ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "NIFTYNXT50"]


# ── Utility functions ──────────────────────────────────────────────────────

def clean_val(val):
    """Convert numpy/pandas data types to standard Python primitives for JSON encoding."""
    if isinstance(val, (np.integer, int)):
        return int(val)
    elif isinstance(val, (np.floating, float)):
        if np.isnan(val) or np.isinf(val):
            return None
        return float(val)
    elif isinstance(val, (np.ndarray, list)):
        return [clean_val(v) for v in val]
    elif isinstance(val, dict):
        return {k: clean_val(v) for k, v in val.items()}
    return val


def sort_dates_chronologically(raw_dates):
    """
    Return date strings sorted chronologically.
    Falls back to raw order if parsing fails.
    """
    import pandas as pd
    try:
        parsed = pd.to_datetime(pd.Series(raw_dates), dayfirst=True, errors="coerce")
        if parsed.isna().any():
            return list(raw_dates)
        order = parsed.sort_values().index
        return [raw_dates[i] for i in order]
    except Exception:
        return list(raw_dates)
