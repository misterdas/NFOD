"""
Telegram Gross OI sender — mirrors the dashboard's Gross OI page as a rich-text
(HTML parse mode) Telegram message after the daily pipeline runs.

Reads the same FDCP_Data.csv the browser dashboard consumes and replicates the
renderDashboardForCurrentDate() table math: 6 instruments × 4 participants with
Longs/Shorts change, Net Today, and Today/1D/2D carried positions, plus the 4
KPI cards from updateKPIs().

Credentials come from env vars (never committed):
    TELEGRAM_BOT_TOKEN   — bot token from @BotFather
    TELEGRAM_CHAT_ID     — target chat/group/channel ID

If either is missing, send_gross_oi_telegram() prints a warning and returns
False so the pipeline can keep going without failing.
"""

import html
import json
import math
import os
import urllib.parse
import urllib.request
from datetime import date, timedelta

import pandas as pd

from nse_toolkit.config import FDCP_FILE, OUTPUT_FILE, sort_dates_chronologically

# Telegram hard limit per text message
MAX_MSG = 4000

# Live dashboard (GitHub Pages) the web-app button opens
DASHBOARD_URL = "https://misterdas.github.io/NFOD/"

# Mirrors app.js INSTRUMENTS (id, title, longCol, shortCol)
INSTRUMENTS = [
    ("Index Futures", "Future Index Long", "Future Index Short"),
    ("Index Calls", "Option Index Call Long", "Option Index Call Short"),
    ("Index Puts", "Option Index Put Long", "Option Index Put Short"),
    ("Stock Futures", "Future Stock Long", "Future Stock Short"),
    ("Stock Calls", "Option Stock Call Long", "Option Stock Call Short"),
    ("Stock Puts", "Option Stock Put Long", "Option Stock Put Short"),
]
PARTICIPANTS = ["Client", "DII", "FII", "Pro"]

GREEN, RED, NEUT = "\U0001F7E2", "\U0001F534", "⚪"  # 🟢 🔴 ⚪


def _inr(v: float | None) -> str:
    """Indian-comma number, sign preserved. '-' when None or NaN."""
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "-"
    return f"{abs(int(v)):,}" if v >= 0 else f"-{abs(int(v)):,}"


def _load_rows():
    """Return dict {date: {participant: row}} sorted chronologically."""
    df = pd.read_csv(FDCP_FILE)
    df.columns = df.columns.str.strip()
    dates = sort_dates_chronologically(list(df["Date"].unique()))
    rows = {}
    for d in dates:
        rows[d] = {r["Client Type"]: r.to_dict() for _, r in df[df["Date"] == d].iterrows()}
    return rows, dates


def _net(row: dict | None, long_col: str, short_col: str) -> float | None:
    if not row:
        return None
    return float(row.get(long_col, 0)) - float(row.get(short_col, 0))


def _chg(today: dict | None, prev: dict | None, col: str) -> float | None:
    if not today or not prev:
        return None
    return float(today.get(col, 0)) - float(prev.get(col, 0))


def build_kpi_message(date: str, rows: dict) -> str:
    """Replicates updateKPIs(): FII futures net, Client/Pro call net, bias.

    Bias = FII futures change + Pro index-call net + Pro index-put net
    (puts signed so that put writing/short-selling — i.e. net short PUT change —
    counts as bullish, while net long PUT buying counts as bearish). The Pro
    put leg was missing and let a single desk's call flow flip the card to
    BULLISH even when Pros were net-selling puts (e.g. -204k on 31-07-2026).
    """
    t = rows[date]
    dates = list(rows.keys())
    idx = dates.index(date) if date in dates else -1
    prev_date = dates[idx - 1] if idx > 0 else None
    p = rows.get(prev_date) if prev_date else None

    fii_t, fii_p = t.get("FII"), (p or {}).get("FII")
    fii_fut_net = (_chg(fii_t, fii_p, "Future Index Long") or 0) - (_chg(fii_t, fii_p, "Future Index Short") or 0) if fii_t and fii_p else None

    cl_t, cl_p = t.get("Client"), (p or {}).get("Client")
    client_calls = (_chg(cl_t, cl_p, "Option Index Call Long") or 0) - (_chg(cl_t, cl_p, "Option Index Call Short") or 0) if cl_t and cl_p else None

    pr_t, pr_p = t.get("Pro"), (p or {}).get("Pro")
    pro_calls = (_chg(pr_t, pr_p, "Option Index Call Long") or 0) - (_chg(pr_t, pr_p, "Option Index Call Short") or 0) if pr_t and pr_p else None
    # Puts: net short change (short - long); writing/selling puts = bullish,
    # net long put buying = bearish protection.
    pro_puts = (_chg(pr_t, pr_p, "Option Index Put Short") or 0) - (_chg(pr_t, pr_p, "Option Index Put Long") or 0) if pr_t and pr_p else None

    bias = (fii_fut_net or 0) + (pro_calls or 0) + (pro_puts or 0)
    if bias > 20000:
        bias_txt, bias_sub = "BULLISH", "Smart Money Buying"
        bias_icon = GREEN
    elif bias < -20000:
        bias_txt, bias_sub = "BEARISH", "Smart Money Selling"
        bias_icon = RED
    else:
        bias_txt, bias_sub = "NEUTRAL / MIXED", "Ranging Positioning"
        bias_icon = NEUT

    def kpi_line(icon, label, val):
        if val is None:
            return f"{icon} <b>{html.escape(label)}:</b> -"
        return f"{GREEN if val >= 0 else RED} <b>{html.escape(label)}:</b> {_inr(val)}"

    lines = [
        f"<b>\U0001F4CA Gross OI — {html.escape(date)}</b>",
        "",
        kpi_line(None, "FII Index Futures (Net)", fii_fut_net),
        kpi_line(None, "Client Index Calls (Net)", client_calls),
        kpi_line(None, "Pro Index Calls (Net)", pro_calls),
        f"{bias_icon} <b>Institutional Bias:</b> {bias_txt} ({html.escape(bias_sub)})",
        "",
    ]
    return "\n".join(lines)


def _days_to_monthly_expiry(d_str: str) -> int | None:
    """
    Days until monthly expiry, mirroring renderGrossOITakeaways() exactly.
    Note: dashboard uses getDay()-2 (last Tuesday proxy), not last Thursday.
    Replicated as-is so Telegram matches the dashboard output.
    """
    try:
        dd, mm, yy = d_str.split("-")
        d0 = date(int(yy), int(mm), int(dd))
        next_first = date(d0.year + (1 if d0.month == 12 else 0), (d0.month % 12) + 1, 1)
        days_back = (next_first.weekday() - 1) % 7 or 7
        expiry = next_first - timedelta(days=days_back)
        return (expiry - d0).days
    except Exception:
        return None


def _monthly_expiry_suffix(r: int | None) -> str:
    if r is None:
        return ""
    if r == 0:
        return "| Monthly Expiry Today"
    if r == 1:
        return "| Monthly Expiry Tomorrow"
    if r == 2:
        return "| Monthly Expiry in 2 Days"
    if 2 <= r <= 5:
        return f"| Monthly Expiry in {r} Days"
    if r == -1:
        return "| Post Monthly Expiry"
    if -7 <= r <= -2:
        return f"| {abs(r)} Days Post Monthly Expiry"
    return ""


def build_takeaways_message() -> str:
    """Key Takeaways from money_flow_data.json participant_summary, mirroring JS."""
    try:
        with open(OUTPUT_FILE) as f:
            ps = json.load(f).get("participant_summary") or {}
    except Exception:
        return ""
    if not ps:
        return ""

    def _a(v):
        return _inr(abs(float(v or 0)))

    l = float(ps.get("smart_money_score") or 0)
    icon = "🟢" if l >= 15 else "🔴" if l <= -15 else "🟡"
    verdict = ("Strongly Bullish" if l >= 40 else "Bullish" if l >= 15
               else "Strongly Bearish" if l <= -40 else "Bearish" if l <= -15 else "Mixed / Neutral")
    lines = [f"{icon} <b>{verdict}</b> — Smart Money Score: <b>{'+' if l > 0 else ''}{l:.2f}</b>"]

    d_str = ps.get("date") or ""
    r = _days_to_monthly_expiry(d_str)
    if d_str:
        lines.append(f"📅 Trading Session: {html.escape(d_str)}{html.escape(_monthly_expiry_suffix(r))}")

    p = float(ps.get("fii_fut_net_change") or 0)
    g = float(ps.get("fii_ce_long_change") or 0)
    h = float(ps.get("fii_ce_short_change") or 0)
    m = float(ps.get("fii_pe_short_change") or 0)
    y = float(ps.get("fii_pe_long_change") or 0)
    f = float(ps.get("fii_stk_fut_net_change") or 0)

    fii_acts = []
    if p > 5000:
        fii_acts.append(f"bought {_a(p)} Index Futures")
    elif p < -5000:
        fii_acts.append(f"sold {_a(p)} Index Futures")
    if g > 20000:
        fii_acts.append(f"bought {_a(g)} Calls")
    if h > 20000:
        fii_acts.append(f"wrote {_a(h)} Calls")
    if m > 20000:
        fii_acts.append(f"wrote {_a(m)} Puts")
    if y > 20000:
        fii_acts.append(f"bought {_a(y)} Puts (hedge)")
    if f > 10000:
        fii_acts.append(f"bought {_a(f)} Stock Futs")
    elif f < -10000:
        fii_acts.append(f"sold {_a(f)} Stock Futs")

    if fii_acts:
        bull = sum([p > 0, g > 10000, m > 10000, f > 10000])
        bear = sum([p < 0, h > 10000, y > 10000, f < -10000])
        o = "🟢" if bull > bear + 1 else "🔴" if bear > bull + 1 else "🟡"
        lines.append(f"{o} <b>FII:</b> {'; '.join(fii_acts)}.")
        carried = float(ps.get("fii_fut_net_carried") or 0)
        if abs(carried) > 100000:
            lines.append(f"📌 FII net carried: {'SHORT' if carried < 0 else 'LONG'} {_a(carried)}")

    pf = float(ps.get("pro_fut_net_change") or 0)
    v = float(ps.get("pro_ce_long_change") or 0)
    b = float(ps.get("pro_pe_short_change") or 0)
    pro_acts = []
    if pf > 5000:
        pro_acts.append(f"bought {_a(pf)} Index Futures")
    elif pf < -5000:
        pro_acts.append(f"sold {_a(pf)} Index Futures")
    if v > 20000:
        pro_acts.append(f"bought {_a(v)} Calls")
    if b > 20000:
        pro_acts.append(f"wrote {_a(b)} Puts")
    if pro_acts:
        lines.append(f"🔥 <b>Pros:</b> {'; '.join(pro_acts)}.")

    x = float(ps.get("client_fut_net_change") or 0)
    w = float(ps.get("client_ce_net_buy") or 0)
    cl_pe = float(ps.get("client_pe_net_buy") or 0)
    retail_acts = []
    if x > 5000:
        retail_acts.append(f"bought {_a(x)} Index Futures")
    elif x < -5000:
        retail_acts.append(f"sold {_a(x)} Index Futures")
    if w > 20000:
        retail_acts.append(f"bought {_a(w)} Calls")
    elif w < -20000:
        retail_acts.append(f"sold {_a(w)} Calls")
    if cl_pe > 20000:
        retail_acts.append(f"bought {_a(cl_pe)} Puts")
    elif cl_pe < -20000:
        retail_acts.append(f"sold {_a(cl_pe)} Puts")
    if retail_acts:
        lines.append(f"👥 <b>Retail:</b> {'; '.join(retail_acts)}.")

    if p > 0 and pf > 0:
        lines.append("🟢 FII + Pros aligned bullish.")
    elif p < 0 and pf < 0:
        lines.append("🔴 FII + Pros aligned bearish.")
    elif p > 0 and pf < -3000:
        lines.append("🟡 FII-Pro divergence — caution.")
    elif p < 0 and pf > 3000:
        lines.append("🟡 Pro-FII tug of war — elevated volatility.")

    trap = ps.get("retail_trap_alarm")
    if trap:
        lines.append(f"🔴 {html.escape(trap)}")
    elif ps.get("retail_confirmation_message"):
        lines.append(f"🟢 {html.escape(ps['retail_confirmation_message'])}")

    if r is None:
        pass
    elif r == 0:
        lines.append("⚠️ Monthly Expiry Today — activity reflects settlement/rollover.")
    elif r == 1:
        lines.append("⚠️ Monthly Expiry Tomorrow — rollover may distort signals.")
    elif 2 <= r <= 5:
        lines.append(f"⚠️ Monthly Expiry in {r} days — watch for rollover.")
    elif -2 <= r < 0:
        lines.append("📌 Post Monthly Expiry — new series building.")

    return "\n".join(lines)


def build_table_message(title, lc, sc, date, prev, prev2, rows, icon):
    """Columnar participant table: Longs/Shorts change and Net (no carried Today/1D/2D)."""
    t, e, _ = rows.get(date), rows.get(prev), rows.get(prev2)
    lines = [f"{icon} <b>{html.escape(title)}</b>", "<pre>"]
    lines.append(f"{'Part':<7}{'Longs':>12}{'Shorts':>12}{'Net':>13}")
    for part in PARTICIPANTS:
        rt, re_ = (t or {}).get(part), (e or {}).get(part)
        lg = _chg(rt, re_, lc)
        sh = _chg(rt, re_, sc)
        net = lg - sh if (lg is not None and sh is not None) else None
        lines.append(f"{part:<7}{_inr(lg):>12}{_inr(sh):>12}{_inr(net):>13}")  # type: ignore[arg-type]
    lines.append("</pre>")
    lines.append("")
    return "\n".join(lines)


def build_gross_oi_messages() -> list[str]:
    """Assemble full-page message chunks (KPI + 6 tables), ≤4000 chars each."""
    rows, dates = _load_rows()
    if not dates:
        return []
    date = dates[-1]
    prev = dates[-2] if len(dates) > 1 else None
    prev2 = dates[-3] if len(dates) > 2 else None

    chunks = [build_kpi_message(date, rows)]
    icons = ["1️⃣", "2️⃣", "3️⃣",
             "4️⃣", "5️⃣", "6️⃣"]
    for (title, lc, sc), icon in zip(INSTRUMENTS, icons):
        msg = build_table_message(title, lc, sc, date, prev, prev2, rows, icon)
        if len("\n".join(chunks) + "\n" + msg) > MAX_MSG:
            chunks.append("")
        chunks[-1] = "\n".join([chunks[-1], msg])

    takeaways = build_takeaways_message()
    if takeaways:
        msg = "\n✅ <b>Key Takeaways</b>\n" + takeaways + "\n"
        if len("\n".join(chunks) + "\n" + msg) > MAX_MSG:
            chunks.append("")
        chunks[-1] = "\n".join([chunks[-1], msg])

    footer = "\n-- 📊 <b>Analysis by GOPAL</b> --"
    if len("\n".join(chunks) + "\n" + footer) > MAX_MSG:
        chunks.append("")
    chunks[-1] = "\n".join([chunks[-1], footer])
    return [c for c in chunks if c.strip()]


def send_message(token: str, chat_id: str, text: str, buttons: list[list[dict]] | None = None) -> bool:
    """Send one HTML message via urllib (stdlib only).

    `buttons` is an InlineKeyboardMarkup row-of-rows, e.g.
    [[{"text": "View Dashboard", "url": DASHBOARD_URL}]].
    """
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": "true",
    }
    if buttons:
        payload["reply_markup"] = json.dumps({"inline_keyboard": buttons})
    data = urllib.parse.urlencode(payload).encode()
    req = urllib.request.Request(url, data=data)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.status == 200


def send_gross_oi_telegram() -> bool:
    """Build + send Gross OI page. Returns False (with warning) if creds missing."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        print("[TELEGRAM] TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set — skipping send.")
        print("[TELEGRAM] Set both env vars to enable. Pipeline continues.")
        return False

    messages = build_gross_oi_messages()
    if not messages:
        print("[TELEGRAM] No FDCP data — nothing to send.")
        return False

    # Dashboard button goes on the last (or only) message
    buttons = [[{"text": "📊 View Dashboard", "url": DASHBOARD_URL}]]
    for i, msg in enumerate(messages):
        send_buttons = buttons if i == len(messages) - 1 else None
        ok = send_message(token, chat_id, msg, buttons=send_buttons)
        if not ok:
            print(f"[TELEGRAM] Failed sending chunk {i + 1}/{len(messages)}")
            return False
    print(f"[TELEGRAM] Sent Gross OI ({len(messages)} message(s)) + dashboard button.")
    return True


if __name__ == "__main__":
    send_gross_oi_telegram()
