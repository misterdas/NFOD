"""
NSE Data Fetcher — uses nsefetch (curl_cffi) to bypass Akamai bot detection.
Fetches option chain data for all F&O stocks and saves compact JSON.
"""
import json
import os
import time
import glob
from datetime import datetime, timezone, timedelta
from nsefetch.config import load_settings
from nsefetch.client import NSEHttpClient

# All active F&O stocks (fallback list)
FNO_STOCKS = [
    "NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "NIFTYNXT50",
    "360ONE", "ABB", "ABCAPITAL", "ADANIENSOL", "ADANIENT", "ADANIGREEN", "ADANIPORTS", "ADANIPOWER",
    "ALKEM", "AMBER", "AMBUJACEM", "ANGELONE", "APLAPOLLO", "APOLLOHOSP", "ASHOKLEY", "ASIANPAINT",
    "ASTRAL", "AUBANK", "AUROPHARMA", "AXISBANK", "BAJAJ-AUTO", "BAJAJFINSV", "BAJAJHLDNG",
    "BAJFINANCE", "BANDHANBNK", "BANKBARODA", "BANKINDIA", "BDL", "BEL", "BHARATFORG", "BHARTIARTL",
    "BHEL", "BIOCON", "BLUESTARCO", "BOSCHLTD", "BPCL", "BRITANNIA", "BSE", "CAMS", "CANBK",
    "CDSL", "CGPOWER", "CHOLAFIN", "CIPLA", "COALINDIA", "COCHINSHIP", "COFORGE", "COLPAL",
    "CONCOR", "CROMPTON", "CUMMINSIND", "DABUR", "DALBHARAT", "DELHIVERY", "DIVISLAB", "DIXON",
    "DLF", "DMART", "DRREDDY", "EICHERMOT", "ETERNAL", "EXIDEIND", "FEDERALBNK", "FORCEMOT",
    "FORTIS", "GAIL", "GLENMARK", "GMRAIRPORT", "GODFRYPHLP", "GODREJCP", "GODREJPROP", "GRASIM",
    "GVT&D", "HAL", "HAVELLS", "HCLTECH", "HDFCAMC", "HDFCBANK", "HDFCLIFE", "HEROMOTOCO",
    "HINDALCO", "HINDPETRO", "HINDUNILVR", "HINDZINC", "HYUNDAI", "ICICIBANK", "ICICIGI",
    "ICICIPRULI", "IDEA", "IDFCFIRSTB", "IEX", "INDHOTEL", "INDIANB", "INDIGO", "INDUSINDBK",
    "INDUSTOWER", "INFY", "INOXWIND", "IOC", "IREDA", "ITC", "JINDALSTEL", "JIOFIN", "JSWENERGY",
    "JSWSTEEL", "JUBLFOOD", "KALYANKJIL", "KAYNES", "KEI", "KFINTECH", "KOTAKBANK", "KPITTECH",
    "LAURUSLABS", "LICHSGFIN", "LICI", "LODHA", "LT", "LTF", "LTM", "LUPIN", "M&M", "MANKIND",
    "MARICO", "MARUTI", "MAXHEALTH", "MAZDOCK", "MCX", "MFSL", "MOTHERSON", "MOTILALOFS",
    "MPHASIS", "MUTHOOTFIN", "NAM-INDIA", "NATIONALUM", "NAUKRI", "NBCC", "NESTLEIND", "NHPC",
    "NMDC", "NTPC", "NUVAMA", "NYKAA", "OBEROIRLTY", "OFSS", "OIL", "ONGC", "PAGEIND",
    "PATANJALI", "PAYTM", "PERSISTENT", "PETRONET", "PFC", "PGEL", "PHOENIXLTD", "PIDILITIND",
    "PIIND", "PNB", "PNBHOUSING", "POLICYBZR", "POLYCAB", "POWERGRID", "POWERINDIA",
    "PREMIERENE", "PRESTIGE", "RADICO", "RBLBANK", "RECLTD", "RELIANCE", "RVNL", "SAIL",
    "SBICARD", "SBILIFE", "SBIN", "SHRIRAMFIN", "SIEMENS", "SOLARINDS", "SONACOMS", "SRF",
    "SUNPHARMA", "SUPREMEIND", "SUZLON", "SWIGGY", "TCS", "TECHM", "TIINDIA", "TITAN",
    "TMPV", "TORNTPHARM", "TRENT", "TVSMOTOR", "ULTRACEMCO", "UNIONBANK", "UNITDSPR",
    "UNOMINDA", "UPL", "VBL", "VEDL", "VMM", "VOLTAS", "WAAREEENER", "WIPRO", "YESBANK",
    "ZYDUSLIFE"
]

OUTPUT_DIR = "docs"


def get_fno_symbols(client):
    """Dynamically fetch active F&O stock symbols from NSE master-quote endpoint."""
    indices = ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "NIFTYNXT50"]
    try:
        master_stocks = client.request_json("GET", "/api/master-quote")
        if isinstance(master_stocks, list) and master_stocks:
            print(f"Fetched {len(master_stocks)} active equity F&O symbols from NSE master-quote.")
            # Remove duplicate indices if present in master_stocks and combine
            stock_list = [s for s in master_stocks if s not in indices]
            return indices + stock_list
    except Exception as e:
        print(f"Warning: Could not fetch master-quote from NSE ({e}). Using static fallback list.")
    
    return FNO_STOCKS


def fetch_one(client, symbol, retries=3):
    """Fetch option chain for a single symbol using nsefetch with retries."""
    for attempt in range(1, retries + 1):
        try:
            # Get expiry dates
            contract_info = client.request_json(
                "GET", "/api/option-chain-contract-info", params={"symbol": symbol}
            )
            if not isinstance(contract_info, dict):
                if attempt < retries:
                    time.sleep(0.5)
                    continue
                print(f"  FAIL {symbol}: Invalid contract info format ({type(contract_info)})")
                return symbol, None

            expiry_dates = contract_info.get("expiryDates", [])
            if not expiry_dates:
                if attempt < retries:
                    time.sleep(0.5)
                    continue
                print(f"  FAIL {symbol}: No expiry dates found in contract info.")
                return symbol, None

            nearest_expiry = expiry_dates[0]

            # Determine type (Indices vs Equity)
            is_index = symbol in {"NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "NIFTYNXT50"}
            chain_type = "Indices" if is_index else "Equity"

            # Fetch option chain
            data = client.request_json(
                "GET",
                "/api/option-chain-v3",
                params={"type": chain_type, "symbol": symbol, "expiry": nearest_expiry},
            )

            if not isinstance(data, dict) or "records" not in data:
                if attempt < retries:
                    time.sleep(0.5)
                    continue
                print(f"  FAIL {symbol}: No records returned in option chain v3.")
                return symbol, None

            records = data["records"]
            underlying = records.get("underlyingValue")
            raw = records.get("data", [])

            # Filter to nearest expiry only (v3 uses "expiryDates" plural)
            # expiryDates may be a string or a single-element list depending on API version
            def _matches_expiry(record):
                ed = record.get("expiryDates")
                if isinstance(ed, list):
                    return len(ed) > 0 and str(ed[0]) == nearest_expiry
                return str(ed) == nearest_expiry if ed else False

            filtered = [r for r in raw if _matches_expiry(r)]

            # Extract compact data
            strikes = []
            for row in filtered:
                ce = row.get("CE", {})
                pe = row.get("PE", {})
                strikes.append({
                    "strike": row.get("strikePrice"),
                    "ce_oi": ce.get("openInterest", 0),
                    "ce_change_oi": ce.get("changeinOpenInterest", 0),
                    "ce_vol": ce.get("totalTradedVolume", 0),
                    "ce_ltp": ce.get("lastPrice", 0),
                    "ce_iv": ce.get("impliedVolatility", 0),
                    "pe_oi": pe.get("openInterest", 0),
                    "pe_change_oi": pe.get("changeinOpenInterest", 0),
                    "pe_vol": pe.get("totalTradedVolume", 0),
                    "pe_ltp": pe.get("lastPrice", 0),
                    "pe_iv": pe.get("impliedVolatility", 0),
                })

            return symbol, {
                "ltp": underlying,
                "expiry": nearest_expiry,
                "strikes": strikes,
            }

        except Exception as e:
            if "blocked" in str(e).lower() or "403" in str(e):
                # Try re-bootstrapping session on block
                try:
                    client.bootstrap_session()
                except Exception:
                    pass
            if attempt < retries:
                time.sleep(0.5 * attempt)
            else:
                print(f"  FAIL {symbol}: {e}")
                return symbol, None

    return symbol, None


def cleanup_old_history(history_dir, max_days=30):
    """Removes archived JSON files older than max_days in docs/oc_history/."""
    if not os.path.exists(history_dir):
        return
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_days)
    for f_path in glob.glob(os.path.join(history_dir, "*.json")):
        try:
            fname = os.path.basename(f_path).replace(".json", "")
            file_date = datetime.strptime(fname, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            if file_date < cutoff:
                os.remove(f_path)
                print(f"  Removed old history snapshot: {f_path}")
        except Exception:
            pass


if __name__ == "__main__":
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat()

    settings = load_settings()
    client = NSEHttpClient(settings=settings)

    print(f"Bootstrapping NSE session...")
    client.bootstrap_session()
    
    symbols_to_fetch = get_fno_symbols(client)
    print(f"Session OK. Fetching {len(symbols_to_fetch)} symbols...")

    results = {}
    success = 0
    fail = 0

    for i, symbol in enumerate(symbols_to_fetch):
        sym, data = fetch_one(client, symbol)
        if data:
            results[sym] = data
            success += 1
        else:
            fail += 1

        # Progress every 20 stocks
        if (i + 1) % 20 == 0 or (i + 1) == len(symbols_to_fetch):
            print(f"  Progress: {i + 1}/{len(symbols_to_fetch)} (ok={success}, fail={fail})")

        # Small delay to avoid rate limiting
        time.sleep(0.2)

    client.close()

    output = {
        "timestamp": timestamp,
        "count": len(results),
        "stocks": results,
    }

    # ── Save current snapshot ──────────────────────────────────────────
    path = os.path.join(OUTPUT_DIR, "nse_data.json")
    with open(path, "w") as f:
        json.dump(output, f)

    # ── Archive daily snapshot for multi-day trend analysis ───────────
    # Each day's snapshot is stored as YYYY-MM-DD.json
    # The verdict engine reads N days of history to build trend vectors.
    history_dir = os.path.join(OUTPUT_DIR, "oc_history")
    os.makedirs(history_dir, exist_ok=True)

    # IST date (UTC+5:30) for consistent date-keying
    ist_now = datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)
    date_key = ist_now.strftime("%Y-%m-%d")

    archive_path = os.path.join(history_dir, f"{date_key}.json")
    with open(archive_path, "w") as f:
        json.dump(output, f)

    # Clean up stale history snapshots (>30 days old) to prevent unbounded growth
    cleanup_old_history(history_dir, max_days=30)

    print(f"\nDone! Saved {len(results)} stocks to {path}")
    print(f"Archived snapshot → {archive_path}")
    print(f"Success: {success}, Failed: {fail}")
    print(f"Timestamp: {timestamp}")
