"""
Static HTML prerenderer — generates static HTML for the dashboard views
so AI URL readers can access market data without JavaScript execution.

Reads FDCP_Data.csv and docs/money_flow_data.json, produces HTML fragments
that mirror what views/gross.js and views/verdict.js generate at runtime,
and injects them into index.html between PRERENDER marker comments.

Also inlines money_flow_data.json as a <script type="application/json"> blob
so data.js can read it synchronously instead of fetching.
"""

import json
import math
import os
import re
import html as html_lib
from datetime import date, datetime, timedelta
from typing import Any

from nse_toolkit.config import (
    FDCP_FILE,
    OUTPUT_FILE,
    sort_dates_chronologically,
    clean_val,
)

INDEX_HTML = "index.html"

# ── Constants mirroring JS views ─────────────────────────────────────────

PARTICIPANTS = ["Client", "DII", "FII", "Pro"]

INSTRUMENTS: list[dict] = [
    {"id": "index-futures", "title": "Index Futures", "l": "Future Index Long", "s": "Future Index Short"},
    {"id": "index-calls", "title": "Index Calls", "l": "Option Index Call Long", "s": "Option Index Call Short"},
    {"id": "index-puts", "title": "Index Puts", "l": "Option Index Put Long", "s": "Option Index Put Short"},
    {"id": "stock-futures", "title": "Stock Futures", "l": "Future Stock Long", "s": "Future Stock Short"},
    {"id": "stock-calls", "title": "Stock Calls", "l": "Option Stock Call Long", "s": "Option Stock Call Short"},
    {"id": "stock-puts", "title": "Stock Puts", "l": "Option Stock Put Long", "s": "Option Stock Put Short"},
]

# Marker pairs in index.html
_GROSS_START = "<!-- PRERENDER:gross -->"
_GROSS_END = "<!-- /PRERENDER:gross -->"
_VERDICT_START = "<!-- PRERENDER:verdict -->"
_VERDICT_END = "<!-- /PRERENDER:verdict -->"
_JSON_MARKER = "[[INLINE_MONEY_FLOW]]"
_JSON_LD_MARKER = "[[INLINE_JSON_LD]]"


# ── Number formatting ─────────────────────────────────────────────────────

def _to_float(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def format_indian_num(v: Any) -> str:
    """Match NFOD.utils.formatIndianNum: en-IN grouping, up to 2 decimals, '-' for null."""
    v = _to_float(v)
    if v is None or math.isnan(v):
        return "-"
    if v == 0:
        return "0"
    neg = v < 0
    abs_v = abs(v)
    int_part = int(abs_v)
    frac = abs_v - int_part

    # Indian-digit grouping: last-3, then groups of 2
    s = str(int_part)
    if len(s) <= 3:
        int_str = s
    else:
        groups = [s[-3:]]
        rest = s[:-3]
        while rest:
            groups.insert(0, rest[-2:])
            rest = rest[:-2]
        int_str = ",".join(groups)

    if frac > 0:
        dec_str = "." + f"{frac:.2f}"[2:].rstrip("0")
    else:
        dec_str = ""

    result = int_str + dec_str
    return f"-{result}" if neg else result


# ── FDCP loading ──────────────────────────────────────────────────────────

def _load_fdcp_rows() -> tuple[dict, list[str]]:
    """Return (rows, dates) where rows = {date: {participant: row_dict}}."""
    import pandas as pd
    df = pd.read_csv(FDCP_FILE)
    df.columns = df.columns.str.strip()
    dates = sort_dates_chronologically(list(df["Date"].unique()))
    rows = {}
    for d in dates:
        rows[d] = {r["Client Type"]: r.to_dict() for _, r in df[df["Date"] == d].iterrows()}
    return rows, dates


def _chg(today: dict | None, prev: dict | None, col: str) -> float | None:
    """Change in a column value (today - prev)."""
    if not today or not prev:
        return None
    return float(today.get(col, 0)) - float(prev.get(col, 0))


# ── Date helpers (mirror JS / telegram) ───────────────────────────────────

def _days_to_monthly_expiry(d_str: str) -> int | None:
    """Mirror NFOD.utils.daysToMonthlyExpiry — last-Tuesday proxy."""
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


# ── HTML helpers ──────────────────────────────────────────────────────────
def _esc(v: Any, quote: bool = True) -> str:
    return html_lib.escape(str(v), quote=quote)


def _cls(v: float | None) -> str:
    """CSS class: pos-up (>=0), pos-down (<0), empty if None."""
    if v is None:
        return ""
    return "pos-up" if v >= 0 else "pos-down"


def _bias_cls(bias: str) -> str:
    if re.search(r"bullish", bias or "", re.IGNORECASE):
        return "bullish"
    if re.search(r"bearish", bias or "", re.IGNORECASE):
        return "bearish"
    return "neutral"


def _val_cell(v: float | None, cls_override: str = "") -> str:
    cls = cls_override or _cls(v)
    return f'<td class="{cls}">{_esc(format_indian_num(v))}</td>'


# ── KPI rendering ─────────────────────────────────────────────────────────

def _kpi_card(h: str, v: float | None, c: str) -> str:
    return (
        '<div class="kpi-card">'
        f'<div class="kpi-header">{_esc(h)}</div>'
        f'<div class="kpi-value {c}">{_esc(format_indian_num(v))}</div>'
        '</div>'
    )


def render_kpis(tm: dict, pm: dict | None) -> str:
    """Mirror views/gross.js renderKPIs()."""
    fii_t = tm.get("FII", {})
    fii_p = pm.get("FII") if pm else None
    client_t = tm.get("Client", {})
    client_p = pm.get("Client") if pm else None
    pro_t = tm.get("Pro", {})
    pro_p = pm.get("Pro") if pm else None

    fii_fut = None
    if fii_t and fii_p:
        fii_fut = _chg(fii_t, fii_p, "Future Index Long") - _chg(fii_t, fii_p, "Future Index Short")

    cl_calls = None
    if client_t and client_p:
        cl_calls = _chg(client_t, client_p, "Option Index Call Long") - _chg(client_t, client_p, "Option Index Call Short")

    pr_calls = None
    pr_puts = None
    if pro_t and pro_p:
        pr_calls = _chg(pro_t, pro_p, "Option Index Call Long") - _chg(pro_t, pro_p, "Option Index Call Short")
        pr_puts = _chg(pro_t, pro_p, "Option Index Put Short") - _chg(pro_t, pro_p, "Option Index Put Long")

    bias = (fii_fut or 0) + (pr_calls or 0) + (pr_puts or 0)
    bias_txt = "BULLISH" if bias > 20000 else "BEARISH" if bias < -20000 else "NEUTRAL / MIXED"
    bias_cls_str = "pos-up" if bias > 0 else ("pos-down" if bias < 0 else "")
    bias_sub = "Score" + (f" +{int(bias)}" if bias > 0 else f" {int(bias)}")

    return (
        '<section class="kpi-bar">'
        f'{_kpi_card("FII Index Futures (Net)", fii_fut, _cls(fii_fut))}'
        f'{_kpi_card("Client Index Calls (Net)", cl_calls, _cls(cl_calls))}'
        f'{_kpi_card("Pro Index Calls (Net)", pr_calls, _cls(pr_calls))}'
        '<div class="kpi-card">'
        f'<div class="kpi-header">Institutional Bias</div>'
        f'<div class="kpi-value {bias_cls_str}">{bias_txt}</div>'
        f'<div class="kpi-sub">{bias_sub}</div>'
        '</div>'
        '</section>'
    )


# ── Instrument table rendering ────────────────────────────────────────────

def render_instrument_table(inst: dict, today_map: dict, prev_map: dict | None, prev2_map: dict | None) -> str:
    """Mirror views/gross.js renderInstrumentTable()."""
    lc, sc = inst["l"], inst["s"]
    rows_html = ""
    for p in PARTICIPANTS:
        r = today_map.get(p, {})
        rp = prev_map.get(p) if prev_map else None
        rp2 = prev2_map.get(p) if prev2_map else None

        long_d = _chg(r, rp, lc) if r and rp else None
        short_d = _chg(r, rp, sc) if r and rp else None
        net = (long_d - short_d) if (long_d is not None and short_d is not None) else None

        carried = (float(r.get(lc, 0)) - float(r.get(sc, 0))) if r else None
        carried1 = (float(rp.get(lc, 0)) - float(rp.get(sc, 0))) if rp else None
        carried2 = (float(rp2.get(lc, 0)) - float(rp2.get(sc, 0))) if rp2 else None

        # Action labels — same logic as gross.js act() / actNet()
        def _act(v, bearish_pos):
            if v is None or v == 0:
                return "-", ""
            if v > 0:
                return "Added", "pos-down" if bearish_pos else "pos-up"
            return "Closed", "pos-up" if bearish_pos else "pos-down"

        def _act_net(v):
            if v is None or v == 0:
                return "-", ""
            if v > 0:
                return "Bought", "pos-up"
            return "Sold", "pos-down"

        la, lc_cls = _act(long_d, False)
        sa, sc_cls = _act(short_d, True)
        na, nc_cls = _act_net(net)

        rows_html += (
            "<tr>"
            f'<td class="sticky-col-first participant">{_esc(p)}</td>'
            f'<td class="action-label {lc_cls}">{_esc(la)}</td>'
            f'<td class="{lc_cls}">{_esc(format_indian_num(long_d))}</td>'
            f'<td class="action-label {sc_cls}">{_esc(sa)}</td>'
            f'<td class="{sc_cls}">{_esc(format_indian_num(short_d))}</td>'
            f'<td class="action-label {nc_cls}">{_esc(na)}</td>'
            f'<td class="{nc_cls}">{_esc(format_indian_num(net))}</td>'
            f'{_val_cell(carried)}'
            f'{_val_cell(carried1)}'
            f'{_val_cell(carried2)}'
            # Trend column — sparkline is JS-only SVG; show carried trend direction as text
            '<td class="spark-cell">—</td>'
            "</tr>"
        )

    return (
        '<div class="instrument-block">'
        f'<div class="block-header">{_esc(inst["title"])}</div>'
        '<div class="table-scroll">'
        '<table class="data-table oi-table">'
        '<colgroup>'
        '<col class="col-participant">'
        '<col class="col-label"><col class="col-value">'
        '<col class="col-label"><col class="col-value">'
        '<col class="col-label"><col class="col-value">'
        '<col class="col-value"><col class="col-value"><col class="col-value">'
        '<col class="col-spark">'
        '</colgroup>'
        '<thead><tr>'
        '<th class="sticky-col-first">Participant</th>'
        '<th colspan="2">Longs</th><th colspan="2">Shorts</th><th colspan="2">Net Today</th>'
        '<th>Today</th><th>1D Ago</th><th>2D Ago</th><th>Trend</th>'
        '</tr></thead>'
        f'<tbody>{rows_html}</tbody>'
        '</table></div></div>'
    )


# ── Right rail rendering ──────────────────────────────────────────────────

def render_right_rail(tm: dict, pm: dict | None) -> str:
    """Mirror views/gross.js renderRightRail()."""
    net_actions: list[dict] = []
    if pm:
        for inst in INSTRUMENTS:
            for p in PARTICIPANTS:
                r = tm.get(p, {})
                rp = pm.get(p)
                if not r or not rp:
                    continue
                net = _chg(r, rp, inst["l"]) - _chg(r, rp, inst["s"])
                if net and net != 0:
                    net_actions.append({"participant": p, "instrument": inst["title"], "action": "Bought" if net > 0 else "Sold", "net": net})

    parts_html = ""
    for p in PARTICIPANTS:
        acts = [a for a in net_actions if a["participant"] == p]
        acts_html = "".join(
            f'<tr><th scope="row" class="action-label">{_esc(a["instrument"])}</th>'
            f'<td class="{_cls(a["net"])}">{_esc(a["action"])}</td>'
            f'<td class="{_cls(a["net"])}">{_esc(format_indian_num(a["net"]))}</td></tr>'
            for a in acts
        ) if acts else '<tr><td colspan="3"><span class="muted">No net change</span></td></tr>'
        parts_html += (
            f'<div class="instrument-block rail-card">'
            f'<div class="block-header">{_esc(p)}</div>'
            '<table class="data-table compact rail-table">'
            '<colgroup><col class="col-inst"><col class="col-act"><col class="col-val"></colgroup>'
            f'{acts_html}'
            '</table></div>'
        )

    return f'<div class="right-rail"><div class="rail-title">Today\'s Action</div>{parts_html}</div>'


# ── Takeaways rendering ──────────────────────────────────────────────────

def render_takeaways(ps: dict | None) -> str:
    """Mirror views/gross.js renderTakeaways()."""
    if not ps:
        return ""
    score = ps.get("smart_money_score", 0) or 0
    icon = "🟢" if score >= 15 else ("🔴" if score <= -15 else "🟡")
    verdict = (
        "Strongly Bullish" if score >= 40 else
        "Bullish" if score >= 15 else
        "Strongly Bearish" if score <= -40 else
        "Bearish" if score <= -15 else
        "Mixed / Neutral"
    )
    score_str = f"+{score}" if score > 0 else str(score)

    lines = [f'{icon} <strong>{_esc(verdict)}</strong> — Smart Money Score: <strong>{_esc(score_str)}</strong>']

    d = ps.get("date") or ""
    if d:
        r = _days_to_monthly_expiry(d)
        suffix = _monthly_expiry_suffix(r)
        lines.append(f"📅 Trading Session: {_esc(d)}{_esc(suffix) if suffix else ''}")

    # FII actions
    fii_acts = []
    def _a(v):
        return format_indian_num(abs(float(v or 0)))

    fii_fut = float(ps.get("fii_fut_net_change") or 0)
    if fii_fut > 5000:
        fii_acts.append(f"bought {_a(fii_fut)} Index Futures")
    elif fii_fut < -5000:
        fii_acts.append(f"sold {_a(fii_fut)} Index Futures")

    fii_ce_lc = float(ps.get("fii_ce_long_change") or 0)
    fii_ce_sc = float(ps.get("fii_ce_short_change") or 0)
    fii_pe_sc = float(ps.get("fii_pe_short_change") or 0)
    fii_pe_lc = float(ps.get("fii_pe_long_change") or 0)

    if fii_ce_lc > 20000:
        fii_acts.append(f"bought {_a(fii_ce_lc)} Calls")
    if fii_ce_sc > 20000:
        fii_acts.append(f"wrote {_a(fii_ce_sc)} Calls")
    if fii_pe_sc > 20000:
        fii_acts.append(f"wrote {_a(fii_pe_sc)} Puts")
    if fii_pe_lc > 20000:
        fii_acts.append(f"bought {_a(fii_pe_lc)} Puts (hedge)")

    if fii_acts:
        lines.append(f"🏛 <strong>FII:</strong> {'; '.join(fii_acts)}.")

    trap = ps.get("retail_trap_alarm")
    if trap:
        lines.append(f"🔴 {_esc(trap)}")
    elif ps.get("retail_confirmation_message"):
        lines.append(f"🟢 {_esc(ps['retail_confirmation_message'])}")

    return (
        '<div class="takeaways">'
        '<div class="takeaways-title">Key Takeaways</div>'
        + "".join(f'<div class="takeaway-item">{l}</div>' for l in lines)
        + "</div>"
    )


# ── Verdict banner rendering ──────────────────────────────────────────────

def render_verdict_banner(ps: dict | None, mf: dict | None) -> str:
    """Mirror views/verdict.js execBanner()."""
    if not ps:
        return (
            '<section class="verdict-banner">'
            '<div class="banner-left">'
            '<div class="banner-row"><span class="badge neutral">NO DATA</span>'
            '<span class="banner-title">INSTITUTIONAL MARKET VERDICT</span></div>'
            '<p class="banner-desc">No verdict computed. Regenerate docs/money_flow_data.json.</p>'
            '</div><div class="banner-right">'
            '<div class="score-label">Smart Money Score</div>'
            '<div class="verdict-gauge">—</div>'
            '</div></section>'
        )

    score = ps.get("smart_money_score", 0)
    bias = ps.get("bias_label", "NEUTRAL")
    action_desc = ps.get("action_desc", "")

    score_f = float(score) if score is not None else 0
    score_str = f"+{score_f:.2f}" if score_f > 0 else f"{score_f:.2f}"
    bias_cls_str = score_f > 0 and "pos-up" or (score_f < 0 and "pos-down" or "")
    b_cls = _bias_cls(bias)

    return (
        '<section class="verdict-banner">'
        f'<div class="banner-left">'
        f'<div class="banner-row"><span class="badge {b_cls}">{_esc(bias)}</span>'
        f'<span class="banner-title">INSTITUTIONAL MARKET VERDICT</span></div>'
        f'<p class="banner-desc">{_esc(action_desc)}</p>'
        f'</div>'
        f'<div class="banner-right">'
        f'<div class="score-label">Smart Money Score</div>'
        f'<div class="verdict-gauge {bias_cls_str}">{_esc(score_str)}</div>'
        f'</div></section>'
    )


def render_stance_panel(ps: dict | None) -> str:
    """Mirror views/verdict.js stancePanel()."""
    if not ps:
        return '<div class="error-card">No participant data.</div>'

    def row(label, val):
        v = format_indian_num(val)
        c = _cls(val)
        return (
            f'<div class="stat-row">'
            f'<span class="stat-label">{_esc(label)}</span>'
            f'<span class="stat-value mono {c}">{_esc(v)}</span>'
            f'</div>'
        )

    return (
        '<div class="instrument-block">'
        '<div class="block-header">FII & Pro Daily Positioning Shift</div>'
        '<div class="panel-body">'
        '<div class="section-label fii">FII (Institutional)</div>'
        f'{row("Call Options Stance", ps.get("fii_ce_net_short_change", 0))}'
        f'{row("Put Options Stance", ps.get("fii_pe_net_short_change", 0))}'
        f'{row("Futures Net Shift", ps.get("fii_fut_net_change", 0))}'
        '<div class="section-label pro">Pro Desk & Retail</div>'
        f'{row("Pro Call Net-Short", ps.get("pro_ce_net_short_change", 0))}'
        f'{row("Pro Put Net-Short", ps.get("pro_pe_net_short_change", 0))}'
        f'{row("Retail Net Calls", ps.get("client_ce_net_buy", 0))}'
        '<div class="section-label dii">DII (Domestic)</div>'
        f'{row("DII Call Shift", ps.get("dii_ce_net_short_change", 0))}'
        f'{row("DII Put Shift", ps.get("dii_pe_net_short_change", 0))}'
        f'{row("DII Futures Net", ps.get("dii_fut_net_change", 0))}'
        '</div></div>'
    )


# ── Main render ───────────────────────────────────────────────────────────

def render_gross_html() -> str:
    """Generate the full Gross OI view as static HTML."""
    try:
        rows, dates = _load_fdcp_rows()
    except Exception as e:
        print(f"[PRERENDER] Cannot load FDCP data: {e}")
        return ""

    if len(dates) < 2:
        print("[PRERENDER] Not enough FDCP dates for KPI comparison.")
        return ""

    latest = dates[-1]
    prev = dates[-2]
    prev2 = dates[-3] if len(dates) > 2 else None

    tm = rows[latest]
    pm = rows[prev]
    p2m = rows[prev2] if prev2 else None

    parts = [render_kpis(tm, pm)]
    parts.append(
        '<main class="dash-grid">'
        f'<div class="main-col">{" ".join(render_instrument_table(i, tm, pm, p2m) for i in INSTRUMENTS)}</div>'
        f'{render_right_rail(tm, pm)}'
        '</main>'
    )

    # Takeaways from money_flow_data.json
    ps = None
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE) as f:
                mf = json.load(f)
            ps = mf.get("participant_summary")
        except Exception:
            pass
    parts.append(render_takeaways(ps))

    return '<div class="noscript-fallback">' + "".join(parts) + '</div>'


def render_verdict_html() -> str:
    """Generate the Verdict view as static HTML (banner + stance panel)."""
    mf = None
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE) as f:
                mf = json.load(f)
        except Exception:
            pass

    if not mf:
        return '<div class="noscript-fallback"><div class="error-card">No verdict data.</div></div>'

    ps = mf.get("participant_summary")
    parts = [render_verdict_banner(ps, mf), render_stance_panel(ps)]
    return '<div class="noscript-fallback">' + "".join(parts) + '</div>'


# ── Inline JSON ───────────────────────────────────────────────────────────

def _build_json_ld(ps: dict | None) -> str:
    """Generate JSON-LD structured data for SEO / AI discoverability."""
    if not ps:
        data = {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": "OI Analysis — Participant OI Dashboard",
            "description": "NSE participant OI analytics — FII/DII/Pro/Client futures & options positioning.",
            "articleSection": "Financial Markets > India > NSE",
        }
    else:
        score = ps.get("smart_money_score", 0)
        bias = ps.get("bias_label", "NEUTRAL")
        date_str = ps.get("date", "")
        data = {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": f"NSE OI Dashboard — {bias}",
            "description": ps.get("action_desc", ""),
            "datePublished": _iso_date(date_str),
            "articleSection": "Financial Markets > India > NSE",
            "articleBody": (
                f"Smart Money Score: {score} | Bias: {bias} | "
                f"FII Futures Net: {format_indian_num(ps.get('fii_fut_net_change'))} | "
                f"Date: {date_str}"
            ),
            "keywords": "NSE, FII, DII, Pro, Client, Open Interest, Option Chain, NIFTY",
            "publisher": {"@type": "Organization", "name": "NFOD"},
        }
    return json.dumps(data, ensure_ascii=False, indent=2)


def _iso_date(d_str: str) -> str:
    """Convert DD-MM-YYYY to ISO YYYY-MM-DD."""
    try:
        dd, mm, yy = d_str.split("-")
        return f"{yy}-{mm}-{dd}"
    except Exception:
        return datetime.utcnow().strftime("%Y-%m-%d")


def _inline_json(html: str) -> str:
    """Embed money_flow_data.json content and JSON-LD into index.html."""
    # Inline money_flow_data.json
    json_str = ""
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE) as f:
                mf = json.load(f)
            # clean numpy types, escape < to prevent </script> breakout
            cleaned = clean_val(mf)
            json_str = json.dumps(cleaned, ensure_ascii=False, indent=2)
            json_str = json_str.replace("<", "\\u003c")
        except Exception as e:
            print(f"[PRERENDER] Cannot inline money_flow_data.json: {e}")

    if _JSON_MARKER in html:
        html = html.replace(_JSON_MARKER, json_str)
    else:
        # Marker already replaced on a previous run — find and replace the
        # content between the inline script tags so subsequent runs update it.
        html = re.sub(
            r'(<script type="application/json" id="inline-money-flow">).*?(</script>)',
            rf'\1{json_str}\2' if json_str else r'\g<0>',
            html,
            flags=re.DOTALL,
        )

    # JSON-LD
    ps = None
    if json_str:
        try:
            mf = json.loads(json_str.replace("\\u003c", "<"))
            ps = mf.get("participant_summary")
        except Exception:
            pass
    json_ld = _build_json_ld(ps)
    html = html.replace(_JSON_LD_MARKER, json_ld)

    return html


# ── Index HTML injection ──────────────────────────────────────────────────

def _inject_section(content: str, start_marker: str, end_marker: str, new_html: str) -> str:
    """Replace content between marker comments in index.html."""
    pattern = re.escape(start_marker) + r".*?" + re.escape(end_marker)
    replacement = start_marker + new_html + end_marker
    new_content, count = re.subn(pattern, replacement, content, count=1, flags=re.DOTALL)
    if count == 0:
        # Markers not found — insert them into the section
        print(f"[PRERENDER] Warning: markers not found, inserting placeholders.")
    return new_content


def prerender_index() -> str:
    """Generate static HTML and inject into index.html. Returns summary string."""
    if not os.path.exists(INDEX_HTML):
        print(f"[PRERENDER] {INDEX_HTML} not found — skipping.")
        return ""

    with open(INDEX_HTML, encoding="utf-8") as f:
        content = f.read()

    # Generate and inject Gross OI HTML
    gross_html = render_gross_html()
    content = _inject_section(content, _GROSS_START, _GROSS_END, gross_html)

    # Generate and inject Verdict HTML
    verdict_html = render_verdict_html()
    content = _inject_section(content, _VERDICT_START, _VERDICT_END, verdict_html)

    # Inline JSON
    content = _inline_json(content)

    with open(INDEX_HTML, "w", encoding="utf-8") as f:
        f.write(content)

    return f"Injected gross ({len(gross_html)} chars), verdict ({len(verdict_html)} chars), inline JSON"


