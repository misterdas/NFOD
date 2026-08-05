"""
CPR (Central Pivot Range) calculation for NSE indices.

CPR formula:
  - Pivot (P)  = (H + L + C) / 3
  - Floor (F)  = (H + L) / 2
  - Ceiling (C)= P + (P - F) = 2*P - F

Data sources:
  - Prior day CPR: H/L from daily candle, C from yesterday's 3:15 1-min candle close
  - Today CPR: H/L from today's daily candle, C from latest 1-min candle close

For closing value use 1min, else use daily candle.
"""
import datetime as dt
import os

import pandas as pd
import yfinance as yf

from .config import clean_val, CPR_SEND_TELEGRAM
from .telegram import send_message

_INDEX_YF = {
    "NIFTY": "^NSEI",
    "BANK": "^NSEBANK",
}


def _resolve(symbol: str) -> str:
    return _INDEX_YF.get(symbol.upper(), symbol)


def _yesterday_315_close(symbol: str) -> float:
    """Get yesterday's 3:15 1-min candle close."""
    ticker = yf.Ticker(_resolve(symbol))
    # Need 2 days of 1-min data to cover yesterday
    hist = ticker.history(period="2d", interval="1m", prepost=False)
    if hist.empty:
        raise RuntimeError(f"No 1-min data for {symbol}")

    yesterday = hist.index[-1].normalize() - pd.Timedelta(days=1)
    # Find 3:15 candle from yesterday's data
    mask = (hist.index == yesterday + pd.Timedelta(hours=15, minutes=15))
    if mask.any():
        return float(hist.loc[mask, "Close"].iloc[-1])
    # Fallback: last candle of yesterday
    today_open = yesterday + pd.Timedelta(hours=6, minutes=15)
    yesterday_data = hist[hist.index < today_open]
    if not yesterday_data.empty:
        return float(yesterday_data["Close"].iloc[-1])
    raise RuntimeError(f"Cannot find yesterday's 3:15 close for {symbol}")


def get_prior_day_hlc(symbol: str = "NIFTY"):
    """Return (high, low, close) for the prior full trading day.

    H/L from daily candle, C from yesterday's 3:15 1-min candle close.
    """
    ticker = yf.Ticker(_resolve(symbol))
    daily = ticker.history(period="5d", interval="1d", prepost=False)
    if daily.empty:
        raise RuntimeError(f"No daily data for {symbol}")
    row = daily.iloc[-2]  # prior day
    h = float(row["High"])
    l = float(row["Low"])
    c = _yesterday_315_close(symbol)
    return h, l, c


def _today_315_close(symbol: str) -> float:
    """Get today's 3:15 1-min candle close (fallback to last candle if unavailable)."""
    ticker = yf.Ticker(_resolve(symbol))
    hist = ticker.history(period="1d", interval="1m", prepost=False)
    if hist.empty:
        raise RuntimeError(f"No 1-min data for {symbol}")
    today = hist.index[-1].normalize()
    target_ts = today + pd.Timedelta(hours=15, minutes=15)
    mask = (hist.index == target_ts)
    if mask.any():
        return float(hist.loc[mask, "Close"].iloc[-1])
    # Fallback: last 1-min candle available today
    return float(hist["Close"].iloc[-1])


def get_today_hlc_dynamic(symbol: str = "NIFTY"):
    """Return today's (high, low, close) dynamically.

    H/L from today's daily candle (so far),
    C from today's 3:15 1-min candle close.
    """
    ticker = yf.Ticker(_resolve(symbol))
    # Daily candle for today's high/low
    daily = ticker.history(period="1d", interval="1d", prepost=False)
    if not daily.empty:
        row = daily.iloc[-1]
        h = float(row["High"])
        l = float(row["Low"])
    else:
        raise RuntimeError(f"No daily data for {symbol}")

    c = _today_315_close(symbol)
    return h, l, c


def calculate_cpr(high: float, low: float, close: float):
    """Standard CPR from High, Low, Close."""
    pivot = (high + low + close) / 3
    floor = (high + low) / 2
    ceiling = pivot + (pivot - floor)  # == 2*pivot - floor
    return {
        "pivot": clean_val(pivot),
        "floor": clean_val(floor),
        "ceiling": clean_val(ceiling),
        "range": clean_val(ceiling - floor),
    }


def get_today_cpr(symbol: str = "NIFTY"):
    """CPR using today's H/L (daily) + latest 1-min close."""
    h, l, c = get_today_hlc_dynamic(symbol)
    cpr = calculate_cpr(h, l, c)
    cpr.update({"symbol": symbol, "high": h, "low": l, "close": c,
                "date": dt.date.today().isoformat(), "source": "today"})
    return cpr


def get_prior_day_cpr(symbol: str = "NIFTY"):
    """CPR using prior day H/L (daily) + yesterday's 3:15 candle close."""
    h, l, c = get_prior_day_hlc(symbol)
    cpr = calculate_cpr(h, l, c)
    cpr.update({"symbol": symbol, "high": h, "low": l, "close": c,
                "date": dt.date.today().isoformat(), "source": "prior_day"})
    return cpr


def _fmt(v) -> str:
    """Comma + 2-decimal number for Telegram."""
    return f"{float(v):,.2f}"


def send_cpr_telegram(symbol: str = "NIFTY") -> bool:
    """Fetch today's CPR for `symbol` and send it to Telegram.

    Credentials from env (same as telegram.py): TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID.
    Returns False (with warning) if creds missing or CPR computation fails.
    """
    if not CPR_SEND_TELEGRAM:
        print("[CPR] CPR_SEND_TELEGRAM=False — skipping send.")
        return False

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        print("[CPR] TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set — skipping send.")
        return False

    try:
        cpr = get_today_cpr(symbol)
    except Exception as e:
        print(f"[CPR] CPR computation failed for {symbol} — {e}")
        return False

    msg = "\n".join([
        "<b>📐 NIFTY — Today's CPR</b>",
        f"📅 {cpr['date']}",
        "",
        f"Pivot (P):   <b>{_fmt(cpr['pivot'])}</b>",
        f"Floor (F):   <b>{_fmt(cpr['floor'])}</b>",
        f"Ceiling (C): <b>{_fmt(cpr['ceiling'])}</b>",
        f"Range (C−F): <b>{_fmt(cpr['range'])}</b>",
    ])
    if not send_message(token, chat_id, msg):
        print("[CPR] Failed sending CPR message.")
        return False
    print(f"[CPR] Sent {symbol} CPR to Telegram.")
    return True


if __name__ == "__main__":
    import sys
    sym = sys.argv[1] if len(sys.argv) > 1 else "NIFTY"
    print("Prior-day CPR:", get_prior_day_cpr(sym))
    print("Today's CPR (dynamic):", get_today_cpr(sym))
