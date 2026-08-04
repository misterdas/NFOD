"""
Unified data fetcher for the NFOD toolkit.

Merges FDCP (NSE participant OI CSV), option chain (jugaad-data), and OHLC (yfinance)
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
from jugaad_data.nse import NSELive

from nse_toolkit.config import (
    FDCP_DAYS,
    OC_WORKERS, OC_DELAY, OC_RETRIES, OC_BLOCK_COOLDOWN,
    OHLC_DAYS,
    ALL_FNO_STOCKS, FETCH_INDICES,
    FDCP_FILE, OUTPUT_DIR, NSE_DATA_FILE, HISTORY_DIR, OHLC_FILE,
)

# Thread-local storage for per-thread NSELive sessions (jugaad-data is NOT thread-safe)
_thread_local = threading.local()


def _get_nse_live() -> NSELive:
    """Get or create a thread-local NSELive session."""
    if not hasattr(_thread_local, "live"):
        _thread_local.live = NSELive()
    return _thread_local.live

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
    Fetch latest FDCP participant OI data and append to existing CSV.
    Iterates from today backwards, skipping dates already present, until
    it hits an existing date (caught up) or `days` is exhausted.
    Returns the number of new rows added.
    """
    end = datetime.now()

    # Collect dates already saved in the CSV
    existing_dates: set[str] = set()
    if os.path.exists(FDCP_FILE):
        try:
            existing_df_check = pd.read_csv(FDCP_FILE)
            existing_df_check.columns = existing_df_check.columns.str.strip()
            existing_dates = set(existing_df_check["Date"].unique())
        except Exception:
            pass

    # Walk back from today, skipping dates already saved
    dates_to_fetch: list[str] = []
    for d in range(days):
        dt = end - timedelta(days=d)
        ddmmyyyy = dt.strftime("%d%m%Y")
        dd_mm_yyyy = dt.strftime("%d-%m-%Y")
        if dd_mm_yyyy in existing_dates:
            break  # caught up — existing data includes this date
        dates_to_fetch.append(ddmmyyyy)

    if not dates_to_fetch:
        _log("[FDCP] Already have latest data. Nothing to fetch.")
        return 0

    dates_to_fetch = dates_to_fetch[::-1]  # chronological order for appending

    _log(f"[FDCP] Fetching participant OI for {len(dates_to_fetch)} new date(s)...")
    frames: list[pd.DataFrame] = []

    for d in dates_to_fetch:
        result = _fetch_fdcp_single_date(d)
        if result is not None:
            frames.append(result)

    if not frames:
        _log("[FDCP] No new data fetched. FDCP_Data.csv not updated.")
        return 0

    new_df = pd.concat(frames, ignore_index=True, axis=0)
    # Strip trailing whitespace from headers (NSE CSV has padded columns)
    new_df.columns = new_df.columns.str.strip()
    new_df = new_df.loc[:, ~new_df.columns.duplicated()]

    # Append to existing CSV, deduplicating by (Client Type, Date)
    if os.path.exists(FDCP_FILE):
        existing_df = pd.read_csv(FDCP_FILE)
        existing_df.columns = existing_df.columns.str.strip()
        existing_df = existing_df.loc[:, ~existing_df.columns.duplicated()]
        combined = pd.concat([existing_df, new_df], ignore_index=True)
        # Keep the last occurrence of each (Client Type, Date) pair
        combined = combined.drop_duplicates(subset=["Client Type", "Date"], keep="last")
        # Sort chronologically by parsed date (DD-MM-YYYY string sort mis-orders across months)
        combined = combined.assign(
            _dt=pd.to_datetime(combined["Date"], format="%d-%m-%Y")
        ).sort_values(["_dt", "Client Type"]).drop(columns="_dt").reset_index(drop=True)
        new_rows = len(combined) - len(existing_df)
        combined.to_csv(FDCP_FILE, index=False)
        _log(f"[FDCP] Merged {len(new_df)} new rows, {new_rows} added (total {len(combined)} rows).")
        return max(0, new_rows)
    else:
        new_df.to_csv(FDCP_FILE, index=False)
        _log(f"[FDCP] Saved {len(new_df)} rows to {FDCP_FILE}.")
        return len(new_df)


# ── Option Chain Fetch ─────────────────────────────────────────────────────

def _matches_expiry(record: dict, nearest_expiry: str) -> bool:
    """Check if a record matches the nearest expiry date."""
    ed = record.get("expiryDates")
    if isinstance(ed, list):
        return len(ed) > 0 and str(ed[0]) == nearest_expiry
    return str(ed) == nearest_expiry if ed else False


def _fetch_one_symbol(
    symbol: str,
    session_blocked: threading.Event,
    session_reset: threading.Event,
) -> tuple[str, Optional[dict]]:
    """Fetch option chain for a single symbol via jugaad-data.

    Uses NSELive.index_option_chain for indices and NSELive.equities_option_chain
    for stocks. jugaad-data returns ALL expiry dates' strikes in one call (vs
    nsefetch's two-call contract-info + chain-v3 flow), so we filter client-side
    using _matches_expiry().

    Thread-local NSELive sessions (one per worker) avoid sharing cookies across
    threads. Anti-bot coordination (session_blocked/session_reset) pauses all
    workers on a 403, lets the first responder sleep through OC_BLOCK_COOLDOWN,
    then invalidates its stale session and lets everyone resume.
    """
    for attempt in range(1, OC_RETRIES + 1):
        try:
            # If another worker hit a block, wait for the global cooldown
            if session_blocked.is_set():
                _log(f"  OC: {symbol} waiting for session reset...")
                session_reset.wait(timeout=OC_BLOCK_COOLDOWN + 10)
                session_blocked.clear()

            live = _get_nse_live()
            if symbol in FETCH_INDICES:
                data = live.index_option_chain(symbol)
            else:
                data = live.equities_option_chain(symbol)

            if not isinstance(data, dict) or "records" not in data:
                if attempt < OC_RETRIES:
                    time.sleep(0.5)
                    continue
                _log(f"  OC: FAIL {symbol} — no records in option chain")
                return symbol, None

            records = data["records"]
            underlying = records.get("underlyingValue")
            raw = records.get("data", [])
            expiry_dates = records.get("expiryDates", [])

            if not expiry_dates:
                if attempt < OC_RETRIES:
                    time.sleep(0.5)
                    continue
                _log(f"  OC: FAIL {symbol} — no expiry dates")
                return symbol, None

            nearest_expiry = expiry_dates[0]
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
            if "blocked" in msg or "403" in msg or "too many" in msg or "rate limit" in msg:
                if not session_blocked.is_set():
                    # First worker to notice the block orchestrates the global pause
                    session_blocked.set()
                    session_reset.clear()
                    _log(f"  OC: Session blocked — cooling down {OC_BLOCK_COOLDOWN}s...")
                    time.sleep(OC_BLOCK_COOLDOWN)
                    # Invalidate this thread's stale session so next call gets a fresh NSELive
                    if hasattr(_thread_local, "live"):
                        del _thread_local.live
                    session_reset.set()
                    _log(f"  OC: Session reset OK, retrying {symbol}...")
                else:
                    # Another worker is already handling the cooldown
                    session_reset.wait(timeout=OC_BLOCK_COOLDOWN + 10)
                if attempt < OC_RETRIES:
                    continue
            elif attempt < OC_RETRIES:
                time.sleep(0.5 * attempt)
            else:
                _log(f"  OC: FAIL {symbol} — {e}")
                return symbol, None

    return symbol, None


def get_fno_symbols() -> list[str]:
    """Fetch current F&O symbols from NSE master-quote via jugaad-data session.

    Falls back to ALL_FNO_STOCKS (static) if the API fails. Indices are appended
    explicitly since master-quote returns stock symbols only.
    """
    try:
        live = _get_nse_live()
        resp = live.s.get(f"{live.base_url}/master-quote", timeout=15)
        if resp.status_code == 200:
            master = resp.json()
            if isinstance(master, list) and master:
                _log(f"[OC] Fetched {len(master)} active F&O symbols from NSE master-quote.")
                # master-quote returns stocks only; add indices explicitly
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

    symbols = get_fno_symbols()
    _log(f"[OC] Fetching {len(symbols)} symbols ({workers} workers)...")

    results: dict[str, dict] = {}
    success = 0
    fail = 0

    session_blocked = threading.Event()
    session_reset = threading.Event()

    with ThreadPoolExecutor(max_workers=workers) as pool:
        fut_map = {
            pool.submit(_fetch_one_symbol, sym, session_blocked, session_reset): sym
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

    return output


def fetch_ohlc(days: int = OHLC_DAYS) -> list[dict]:
    """
    Fetch NIFTY OHLC data via yfinance and append to existing JSON.
    Only fetches dates newer than the last record in docs/ohlc_data.json,
    falling back to a `days`-day window when no history exists.
    Saves to docs/ohlc_data.json. Returns all records (existing + new).
    """
    # Load existing data to find the latest date we already have
    existing_records: list[dict] = []
    latest_date: str | None = None
    if os.path.exists(OHLC_FILE):
        try:
            with open(OHLC_FILE) as f:
                existing_data = json.load(f)
            existing_records = existing_data.get("nifty", [])
            if existing_records:
                latest_date = max(r["date"] for r in existing_records)
        except Exception:
            pass

    end_date = (datetime.now() + timedelta(days=1)).date()
    if latest_date:
        start_date = datetime.strptime(latest_date, "%Y-%m-%d").date() + timedelta(days=1)
        # Already have today's data — nothing to fetch
        if datetime.strptime(latest_date, "%Y-%m-%d").date() >= datetime.now().date():
            _log(f"[OHLC] Already have latest data (last: {latest_date}). Nothing to fetch.")
            return existing_records
    else:
        start_date = end_date - timedelta(days=days)

    _log(f"[OHLC] Fetching NIFTY OHLC from {start_date.isoformat()} to {end_date.isoformat()}...")

    ticker = yf.Ticker("^NSEI")
    df = ticker.history(start=start_date.isoformat(), end=end_date.isoformat())

    if df.empty:
        _log("[OHLC] Warning: No new data returned.")
        new_records: list[dict] = []
    else:
        new_records = []
        for idx, row in df.iterrows():
            if isinstance(idx, pd.Timestamp):
                d = idx.date().isoformat()
            else:
                d = str(idx).split()[0]
            new_records.append({
                "date": d,
                "open": round(float(row["Open"]), 2),  # type: ignore[reportArgumentType]
                "high": round(float(row["High"]), 2),  # type: ignore[reportArgumentType]
                "low": round(float(row["Low"]), 2),  # type: ignore[reportArgumentType]
                "close": round(float(row["Close"]), 2),  # type: ignore[reportArgumentType]
                "volume": int(row["Volume"]) if bool(pd.notna(row["Volume"])) else 0,  # type: ignore[reportArgumentType]
            })
        _log(f"  {new_records[0]['date']} -> {new_records[-1]['date']} ({len(new_records)} new records)")

    # Merge: existing + new, dedup by date (keep latest)
    all_by_date: dict[str, dict] = {r["date"]: r for r in existing_records}
    for r in new_records:
        all_by_date[r["date"]] = r
    merged = sorted(all_by_date.values(), key=lambda x: x["date"])

    data = {"nifty": merged, "fetched_at": datetime.now().strftime("%Y-%m-%d")}
    with open(OHLC_FILE, "w") as f:
        json.dump(data, f, indent=2)

    _log(f"[OHLC] Saved {len(merged)} total NIFTY records to {OHLC_FILE} ({len(new_records)} new)")
    return merged


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
