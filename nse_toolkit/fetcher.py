"""
Unified data fetcher for the NFOD toolkit.

Merges FDCP (NSE participant OI CSV), option chain (nsefetch), and OHLC (yfinance)
fetching into a single module with parallel download support.
"""

import glob
import io
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from typing import Optional

import pandas as pd
import requests
import yfinance as yf
from nsefetch.config import load_settings
from nsefetch.client import NSEHttpClient

from nse_toolkit.config import (
    FDCP_DAYS,
    OC_WORKERS, OC_DELAY, OC_RETRIES, OC_BLOCK_COOLDOWN,
    OC_BREAKER_BLOCK_THRESHOLD, OC_BREAKER_FAILURE_THRESHOLD, OC_BREAKER_COOLDOWN,
    OHLC_DAYS,
    ALL_FNO_STOCKS, FETCH_INDICES,
    FDCP_FILE, OUTPUT_DIR, NSE_DATA_FILE, HISTORY_DIR, OHLC_FILE,
)

# Thread-safe print lock
_print_lock = threading.Lock()


def _log(msg: str):
    with _print_lock:
        print(msg)


# ── FDCP Fetch ─────────────────────────────────────────────────────────────

def _fetch_fdcp_single_date(date_str: str) -> Optional[pd.DataFrame]:
    """Fetch FDCP CSV for a single date and return a DataFrame with a Date column."""
    url = f"https://archives.nseindia.com/content/nsccl/fao_participant_oi_{date_str}.csv"
    try:
        resp = requests.get(url, timeout=15)
        df = pd.read_csv(io.StringIO(resp.content.decode("utf-8")), skiprows=1)
        df["Date"] = datetime.strptime(date_str, "%d%m%Y").strftime("%d-%m-%Y")
        _log(f"  FDCP: Done for {df['Date'].iloc[0]}")
        return df
    except Exception:
        _log(f"  FDCP: No data for {date_str}")
        return None


def fetch_fdcp(days: int = FDCP_DAYS) -> int:
    """
    Fetch FDCP participant OI data for the last `days` days (sequential).
    Saves to FDCP_Data.csv. Returns the number of rows written.
    """
    end = datetime.now()
    dates = [(end - timedelta(days=d)).strftime("%d%m%Y") for d in range(days)]
    dates = dates[::-1]  # chronological order

    _log(f"[FDCP] Fetching participant OI for {len(dates)} days...")
    frames: list[pd.DataFrame] = []

    for d in dates:
        result = _fetch_fdcp_single_date(d)
        if result is not None:
            frames.append(result)

    if not frames:
        _log("[FDCP] No data fetched. FDCP_Data.csv not updated.")
        return 0

    df = pd.concat(frames, ignore_index=True, axis=0)
    df.to_csv(FDCP_FILE, index=False)
    _log(f"[FDCP] Saved {len(df)} rows to {FDCP_FILE}.")
    return len(df)


# ── Option Chain Fetch ─────────────────────────────────────────────────────

def _matches_expiry(record: dict, nearest_expiry: str) -> bool:
    """Check if a record matches the nearest expiry date."""
    ed = record.get("expiryDates")
    if isinstance(ed, list):
        return len(ed) > 0 and str(ed[0]) == nearest_expiry
    return str(ed) == nearest_expiry if ed else False


def _fetch_one_symbol(
    client: NSEHttpClient,
    symbol: str,
    session_blocked: threading.Event,
    session_reset: threading.Event,
) -> tuple[str, Optional[dict]]:
    """Fetch option chain for a single symbol with retry and coordinated session reset.

    When NSE's anti-bot blocks a request, the first worker to notice pauses all
    workers (via the shared events), waits out the block with a bounded cooldown,
    force-refreshes the session cookies, and lets everyone resume — instead of the
    old behavior where each blocked request consumed a retry and the whole tail of
    symbols failed once nsefetch's internal circuit breaker opened.
    """
    for attempt in range(1, OC_RETRIES + 1):
        try:
            # If another worker hit a block, wait for the global cooldown + reset
            if session_blocked.is_set():
                _log(f"  OC: {symbol} waiting for session reset...")
                session_reset.wait(timeout=OC_BLOCK_COOLDOWN + 10)
                session_blocked.clear()

            contract_info = client.request_json(
                "GET", "/api/option-chain-contract-info", params={"symbol": symbol}
            )
            if not isinstance(contract_info, dict):
                if attempt < OC_RETRIES:
                    time.sleep(0.5)
                    continue
                return symbol, None

            expiry_dates = contract_info.get("expiryDates", [])
            if not expiry_dates:
                if attempt < OC_RETRIES:
                    time.sleep(0.5)
                    continue
                _log(f"  OC: FAIL {symbol} — no expiry dates")
                return symbol, None

            nearest_expiry = expiry_dates[0]
            is_index = symbol in FETCH_INDICES
            chain_type = "Indices" if is_index else "Equity"

            data = client.request_json(
                "GET", "/api/option-chain-v3",
                params={"type": chain_type, "symbol": symbol, "expiry": nearest_expiry},
            )

            if not isinstance(data, dict) or "records" not in data:
                if attempt < OC_RETRIES:
                    time.sleep(0.5)
                    continue
                _log(f"  OC: FAIL {symbol} — no records in option chain v3")
                return symbol, None

            records = data["records"]
            underlying = records.get("underlyingValue")
            raw = records.get("data", [])

            filtered = [r for r in raw if _matches_expiry(r, nearest_expiry)]

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

            return symbol, {"ltp": underlying, "expiry": nearest_expiry, "strikes": strikes}

        except Exception as e:
            msg = str(e).lower()
            if "blocked" in msg or "403" in msg or "circuit breaker" in msg or "half-open" in msg:
                if not session_blocked.is_set():
                    # First worker to notice the block orchestrates the global pause
                    session_blocked.set()
                    session_reset.clear()
                    _log(f"  OC: Session blocked — cooling down {OC_BLOCK_COOLDOWN}s, "
                         f"then re-bootstrapping...")
                    try:
                        # Wait out NSE's anti-bot window before re-syncing cookies
                        time.sleep(OC_BLOCK_COOLDOWN)
                        client.bootstrap_session(force=True)
                        session_reset.set()
                        _log(f"  OC: Session reset OK, retrying {symbol}...")
                    except Exception as be:
                        _log(f"  OC: Session reset failed: {be}")
                        session_reset.set()
                else:
                    # Another worker is already handling the reset
                    session_reset.wait(timeout=OC_BLOCK_COOLDOWN + 10)
                if attempt < OC_RETRIES:
                    continue
            elif attempt < OC_RETRIES:
                time.sleep(0.5 * attempt)
            else:
                _log(f"  OC: FAIL {symbol} — {e}")
                return symbol, None

    return symbol, None


def get_fno_symbols(client: NSEHttpClient) -> list[str]:
    """Fetch active F&O symbols from NSE master-quote, with static fallback."""
    try:
        master = client.request_json("GET", "/api/master-quote")
        if isinstance(master, list) and master:
            _log(f"[OC] Fetched {len(master)} active F&O symbols from NSE master-quote.")
            return [s for s in master if s not in FETCH_INDICES] + FETCH_INDICES
    except Exception as e:
        _log(f"[OC] Warning: master-quote failed ({e}). Using static fallback.")
    return ALL_FNO_STOCKS


def fetch_option_chain(workers: int = OC_WORKERS) -> dict:
    """
    Fetch option chain data for all F&O symbols using parallel workers.
    Saves current snapshot to docs/nse_data.json and archives a daily copy.
    Returns the results dict.
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    history_dir = HISTORY_DIR
    os.makedirs(history_dir, exist_ok=True)

    timestamp = datetime.now(timezone.utc).isoformat()

    _log("[OC] Bootstrapping NSE session...")
    settings = load_settings(
        circuit_breaker_block_threshold=OC_BREAKER_BLOCK_THRESHOLD,
        circuit_breaker_failure_threshold=OC_BREAKER_FAILURE_THRESHOLD,
        circuit_breaker_cooldown_seconds=OC_BREAKER_COOLDOWN,
    )
    client = NSEHttpClient(settings=settings)
    client.bootstrap_session()

    symbols = get_fno_symbols(client)
    _log(f"[OC] Session OK. Fetching {len(symbols)} symbols ({workers} workers)...")

    results: dict[str, dict] = {}
    success = 0
    fail = 0

    session_blocked = threading.Event()
    session_reset = threading.Event()

    with ThreadPoolExecutor(max_workers=workers) as pool:
        fut_map = {
            pool.submit(_fetch_one_symbol, client, sym, session_blocked, session_reset): sym
            for sym in symbols
        }
        for i, fut in enumerate(as_completed(fut_map), 1):
            sym, data = fut.result()
            if data:
                results[sym] = data
                success += 1
            else:
                fail += 1
            if i % 20 == 0 or i == len(symbols):
                _log(f"  OC: Progress {i}/{len(symbols)} (ok={success}, fail={fail})")
            time.sleep(OC_DELAY)  # gentle pacing

    client.close()

    output = {"timestamp": timestamp, "count": len(results), "stocks": results}

    # Save current snapshot
    with open(NSE_DATA_FILE, "w") as f:
        json.dump(output, f)

    # Archive daily snapshot
    ist_now = datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)
    date_key = ist_now.strftime("%Y-%m-%d")
    archive_path = os.path.join(history_dir, f"{date_key}.json")
    with open(archive_path, "w") as f:
        json.dump(output, f)

    cleanup_old_history(history_dir, max_days=30)

    _log(f"[OC] Done! Saved {len(results)} stocks to {NSE_DATA_FILE}")
    _log(f"[OC] Archived → {archive_path}")
    _log(f"[OC] Success: {success}, Failed: {fail}")
    return results


# ── OHLC Fetch ─────────────────────────────────────────────────────────────

def fetch_ohlc(days: int = OHLC_DAYS) -> list[dict]:
    """
    Fetch NIFTY OHLC data for the last `days` days via yfinance.
    Saves to docs/ohlc_data.json. Returns the records list.
    """
    end_date = (datetime.now() + timedelta(days=1)).date()
    start_date = (end_date - timedelta(days=days))

    _log(f"[OHLC] Fetching NIFTY OHLC ({days}-day window)...")

    ticker = yf.Ticker("^NSEI")
    df = ticker.history(start=start_date.isoformat(), end=end_date.isoformat())

    if df.empty:
        _log("[OHLC] Warning: No data returned.")
        records: list[dict] = []
    else:
        records = []
        for idx, row in df.iterrows():
            if isinstance(idx, pd.Timestamp):
                d = idx.date().isoformat()
            else:
                d = str(idx).split()[0]
            records.append({
                "date": d,
                "open": round(float(row["Open"]), 2),
                "high": round(float(row["High"]), 2),
                "low": round(float(row["Low"]), 2),
                "close": round(float(row["Close"]), 2),
                "volume": int(row["Volume"]),
            })
        _log(f"  {records[0]['date']} -> {records[-1]['date']} ({len(records)} records)")

    data = {"nifty": records, "fetched_at": datetime.now().strftime("%Y-%m-%d")}
    with open(OHLC_FILE, "w") as f:
        json.dump(data, f, indent=2)

    _log(f"[OHLC] Saved {len(records)} NIFTY records to {OHLC_FILE}")
    return records


# ── History cleanup (shared) ───────────────────────────────────────────────

def cleanup_old_history(history_dir: str, max_days: int = 30) -> None:
    """Remove archived JSON files older than max_days from history_dir."""
    if not os.path.exists(history_dir):
        return
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_days)
    for f_path in glob.glob(os.path.join(history_dir, "*.json")):
        try:
            fname = os.path.basename(f_path).replace(".json", "")
            file_date = datetime.strptime(fname, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            if file_date < cutoff:
                os.remove(f_path)
                _log(f"  Removed old history snapshot: {f_path}")
        except Exception:
            pass


# ── Embedded CSV updater ───────────────────────────────────────────────────

def update_embedded_csv() -> None:
    """Rebuild the embedded CSV string in app.js from FDCP_Data.csv."""
    appjs_path = "data.js"
    if not os.path.exists(FDCP_FILE) or not os.path.exists(appjs_path):
        _log("[EMBED] FDCP_Data.csv or data.js not found — skipping embedded CSV update.")
        return

    import csv as csv_mod

    try:
        # Read FDCP_Data.csv into a SQL-style string (comma-first, \r\n delimiters)
        with open(FDCP_FILE, newline="", encoding="utf-8") as f:
            rows = list(csv_mod.reader(f))

        if not rows:
            _log("[EMBED] No rows in FDCP_Data.csv — skipping.")
            return

        header = ",".join(rows[0])
        data_lines = [",".join(row) for row in rows[1:]]
        csv_string = header + "\\r\\n" + "\\r\\n".join(data_lines) + "\\r\\n"

        # Read current app.js
        with open(appjs_path, encoding="utf-8") as f:
            content = f.read()

        # Find the embedded CSV boundaries
        prefix = 'var _EMBEDDED_CSV="'
        suffix = '";let rawCSVData='

        start = content.find(prefix)
        if start == -1:
            _log(f"[EMBED] Could not find _EMBEDDED_CSV in {appjs_path} — skipping.")
            return

        # Content begins right after the opening quote
        content_start = start + len(prefix)
        end = content.find(suffix, content_start)
        if end == -1:
            _log(f"[EMBED] Could not find closing of _EMBEDDED_CSV in {appjs_path} — skipping.")
            return

        # Build replacement
        new_content = content[:content_start] + csv_string + content[end:]
        with open(appjs_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        date_count = len(data_lines) // 5
        _log(f"[EMBED] Updated {appjs_path} embedded CSV ({date_count} dates).")

    except Exception as e:
        _log(f"[EMBED] Error updating embedded CSV: {e}")
