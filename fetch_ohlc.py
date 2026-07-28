"""Fetch NIFTY & BANKNIFTY OHLC data for last 45 days using yfinance."""
import json
import yfinance as yf
from datetime import date, timedelta

end_date = date.today()
start_date = end_date - timedelta(days=45)

def fetch_snapshot(symbol, name):
    ticker = yf.Ticker(symbol)
    df = ticker.history(start=start_date.isoformat(), end=end_date.isoformat())
    if df.empty:
        print(f"Warning: No data for {symbol}")
        return []
    records = []
    for idx, row in df.iterrows():
        d = idx.date().isoformat() if hasattr(idx, 'date') else str(idx).split()[0]
        records.append({
            "date": d,
            "open": round(float(row["Open"]), 2),
            "high": round(float(row["High"]), 2),
            "low": round(float(row["Low"]), 2),
            "close": round(float(row["Close"]), 2),
            "volume": int(row["Volume"])
        })
    print(f"  {name}: {len(records)} records from {records[0]['date']} to {records[-1]['date']}")
    return records

print("Fetching OHLC data...")
data = {
    "nifty": fetch_snapshot("^NSEI", "NIFTY"),
    "banknifty": fetch_snapshot("^NSEBANK", "BANKNIFTY"),
    "fetched_at": date.today().isoformat()
}

with open("docs/ohlc_data.json", "w") as f:
    json.dump(data, f, indent=2)

print(f"Saved to docs/ohlc_data.json ({len(data['nifty'])} NIFTY, {len(data['banknifty'])} BANKNIFTY records)")
