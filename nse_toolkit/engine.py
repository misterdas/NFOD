"""
Institutional Verdict Engine — Money Flow & Market Breadth Analysis.

Cross-correlates Gross Participant OI (FDCP_Data.csv) with Strike-Level Option Chains
(nse_data.json) and multi-day snapshot archives (docs/oc_history/) to deliver
institutional verdicts.

Participant weighting philosophy (explicit, by design):
    FII  weight = 1.00  (largest, most informationally significant flows)
    Pro  weight = 0.60  (prop desks / arbitrageurs — meaningful but often hedge-driven)
    DII  weight = 0.40  (mutual funds/insurers — slower-moving, still directional signal)
    Client (retail) is NEVER scored directly. It is only used as a contrarian
    overlay ("trapped retail") that nudges the score when retail is heavily
    positioned against what FII is doing — i.e. the lowest-priority participant
    only matters in how it confirms/contradicts the higher-priority ones.
"""

import glob
import json
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from nse_toolkit.config import (
    FDCP_FILE, NSE_DATA_FILE, HISTORY_DIR, OUTPUT_FILE,
    CHANGES_FILE, CHANGES_KEYS, CHANGES_DAYS,
    FII_WEIGHT, PRO_WEIGHT, DII_WEIGHT,
    FII_FUT_THRESHOLD, FII_OPT_THRESHOLD,
    PRO_FUT_THRESHOLD, PRO_OPT_THRESHOLD,
    DII_FUT_THRESHOLD, DII_OPT_THRESHOLD,
    RETAIL_TRAP_THRESHOLD, SCORE_CLIP,
    IV_MOD_MAX, IV_MOD_BOOST, IV_HIGH_THRESH, IV_LOW_THRESH,
    INDICES,
    clean_val, sort_dates_chronologically,
)
from nse_toolkit.fetcher import cleanup_old_history


# ── IV Modifier ─────────────────────────────────────────────────────────────

def compute_iv_modifier(stocks: dict) -> float:
    """
    Compute an IV-based confidence modifier for the composite score.
    Higher IV → noisier market → reduce conviction (negative modifier).
    Lower IV → clearer signal → increase conviction (positive modifier).
    Uses ATM strike IVs across all tracked indices.
    """
    ivs: list[float] = []
    for sym in INDICES:
        if sym not in stocks:
            continue
        data = stocks[sym]
        ltp = data.get("ltp")
        strikes = data.get("strikes", [])
        if not ltp or not strikes:
            continue
        near = [s for s in strikes if abs(s["strike"] - ltp) / ltp <= 0.02]
        for s in near:
            ce_iv = s.get("ce_iv", 0)
            if ce_iv and ce_iv > 0:
                ivs.append(ce_iv)
            pe_iv = s.get("pe_iv", 0)
            if pe_iv and pe_iv > 0:
                ivs.append(pe_iv)
    if not ivs:
        return 0.0
    avg_iv = float(np.mean(ivs))
    if avg_iv > IV_HIGH_THRESH:
        return -min(IV_MOD_MAX, (avg_iv - IV_HIGH_THRESH) * 0.5)
    elif avg_iv < IV_LOW_THRESH:
        return min(IV_MOD_BOOST, (IV_LOW_THRESH - avg_iv) * 1.0)
    return 0.0


# ── FDCP Participant Data Loader ───────────────────────────────────────────

def _calc_chg(row_t: dict, row_p: dict | None, col: str) -> float:
    if row_t and row_p:
        return float(row_t.get(col, 0)) - float(row_p.get(col, 0))
    return 0.0


def _load_participant_changes(row_t: dict, row_p: dict | None) -> dict:
    """
    Returns net directional changes for one participant across all instruments.
    Long and short legs are ALWAYS netted together before anything downstream
    uses them — a participant adding both long and short calls at once should
    not register as pure directional writing.
    """
    fut_long = _calc_chg(row_t, row_p, "Future Index Long")
    fut_short = _calc_chg(row_t, row_p, "Future Index Short")
    ce_long = _calc_chg(row_t, row_p, "Option Index Call Long")
    ce_short = _calc_chg(row_t, row_p, "Option Index Call Short")
    pe_long = _calc_chg(row_t, row_p, "Option Index Put Long")
    pe_short = _calc_chg(row_t, row_p, "Option Index Put Short")
    stk_fut_long = _calc_chg(row_t, row_p, "Future Stock Long")
    stk_fut_short = _calc_chg(row_t, row_p, "Future Stock Short")
    stk_ce_long = _calc_chg(row_t, row_p, "Option Stock Call Long")
    stk_ce_short = _calc_chg(row_t, row_p, "Option Stock Call Short")
    stk_pe_long = _calc_chg(row_t, row_p, "Option Stock Put Long")
    stk_pe_short = _calc_chg(row_t, row_p, "Option Stock Put Short")

    return {
        "fut_chg": fut_long - fut_short,
        "fut_long_chg": fut_long,
        "fut_short_chg": fut_short,
        "ce_long_chg": ce_long,
        "ce_short_chg": ce_short,
        "pe_long_chg": pe_long,
        "pe_short_chg": pe_short,
        "ce_net_short_chg": ce_short - ce_long,
        "pe_net_short_chg": pe_short - pe_long,
        "stk_fut_chg": stk_fut_long - stk_fut_short,
        "stk_fut_long_chg": stk_fut_long,
        "stk_fut_short_chg": stk_fut_short,
        "stk_ce_long_chg": stk_ce_long,
        "stk_ce_short_chg": stk_ce_short,
        "stk_pe_long_chg": stk_pe_long,
        "stk_pe_short_chg": stk_pe_short,
    }


def _participant_score(p: dict, fut_th: float, opt_th: float) -> int:
    """
    Proportional scoring: base ±15 for crossing threshold, plus up to ±10
    proportional to how far beyond the threshold. Max ±25 per leg.
    Positive = net bullish (buying futures, covering calls, writing puts).
    Negative = net bearish (selling futures, writing calls, unwinding puts).
    """
    s = 0.0

    # Futures
    if p["fut_chg"] > fut_th:
        ratio = min(1.0, (p["fut_chg"] - fut_th) / fut_th)
        s += 15 + round(ratio * 10)
    elif p["fut_chg"] < -fut_th:
        ratio = min(1.0, (abs(p["fut_chg"]) - fut_th) / fut_th)
        s -= 15 + round(ratio * 10)

    # Call options — negative net short change = covering (bullish), positive = writing (bearish)
    if p["ce_net_short_chg"] < -opt_th:
        ratio = min(1.0, (abs(p["ce_net_short_chg"]) - opt_th) / opt_th)
        s += 15 + round(ratio * 10)
    elif p["ce_net_short_chg"] > opt_th:
        ratio = min(1.0, (p["ce_net_short_chg"] - opt_th) / opt_th)
        s -= 15 + round(ratio * 10)

    # Put options — positive net short change = writing floor (bullish), negative = unwinding (bearish)
    if p["pe_net_short_chg"] > opt_th:
        ratio = min(1.0, (p["pe_net_short_chg"] - opt_th) / opt_th)
        s += 15 + round(ratio * 10)
    elif p["pe_net_short_chg"] < -opt_th:
        ratio = min(1.0, (abs(p["pe_net_short_chg"]) - opt_th) / opt_th)
        s -= 15 + round(ratio * 10)

    return max(-25, min(25, int(s)))


def _score_date_pair(
    fii_today: dict, fii_prev: dict | None,
    pro_today: dict, pro_prev: dict | None,
    dii_today: dict, dii_prev: dict | None,
    client_today: dict, client_prev: dict | None,
    latest_date: str | None, prev_date: str | None,
    iv_modifier: float = 0.0,
) -> dict:
    """Full flat participant_summary dict for one (today, prev) FDCP pair.

    Shared by `load_participant_data` (latest pair, live IV modifier) and
    `build_score_history` (every historical pair, IV modifier 0) so per-date
    scores use identical math — never re-implement scoring in two places.
    """
    fii = _load_participant_changes(fii_today, fii_prev)
    pro = _load_participant_changes(pro_today, pro_prev)
    dii = _load_participant_changes(dii_today, dii_prev)
    client = _load_participant_changes(client_today, client_prev)

    # Client (Retail) net buy — used ONLY for the contrarian trap overlay
    client_ce_net_buy = client["ce_long_chg"] - client["ce_short_chg"]
    client_pe_net_buy = client["pe_long_chg"] - client["pe_short_chg"]

    fii_raw_score = _participant_score(fii, FII_FUT_THRESHOLD, FII_OPT_THRESHOLD)
    pro_raw_score = _participant_score(pro, PRO_FUT_THRESHOLD, PRO_OPT_THRESHOLD)
    dii_raw_score = _participant_score(dii, DII_FUT_THRESHOLD, DII_OPT_THRESHOLD)

    # Explicit weighted composite: FII > Pro > DII. Client excluded by design.
    weighted_score = (
        fii_raw_score * FII_WEIGHT
        + pro_raw_score * PRO_WEIGHT
        + dii_raw_score * DII_WEIGHT
    )
    weighted_score = max(-SCORE_CLIP, min(SCORE_CLIP, weighted_score))

    # FII-DII Alignment Modifier
    fii_dii_modifier = 0
    if fii_raw_score > 0 and dii_raw_score > 0:
        fii_dii_modifier = min(10, abs(fii_raw_score) * abs(dii_raw_score) / 200)
    elif fii_raw_score < 0 and dii_raw_score < 0:
        fii_dii_modifier = min(10, abs(fii_raw_score) * abs(dii_raw_score) / 200)
    elif fii_raw_score * dii_raw_score < 0:
        fii_dii_modifier = -min(10, abs(fii_raw_score) * abs(dii_raw_score) / 200)

    # Retail Trap / Contrarian Sentiment Filter
    retail_trap_alarm: str | None = None
    trap_adjustment = 0
    retail_confirmation_message: str | None = None
    retail_confirmation_score = 0

    if client_ce_net_buy > RETAIL_TRAP_THRESHOLD and fii["ce_net_short_chg"] > FII_OPT_THRESHOLD:
        trap_adjustment = -15
        retail_trap_alarm = "RETAIL CALL TRAP ALERT: Retail buying calls while FIIs aggressively write calls."
    elif client_pe_net_buy > RETAIL_TRAP_THRESHOLD and fii["pe_net_short_chg"] > FII_OPT_THRESHOLD:
        trap_adjustment = 15
        retail_trap_alarm = "RETAIL PUT TRAP ALERT: Retail buying puts while FIIs aggressively write puts."

    if trap_adjustment == 0:
        if client_ce_net_buy < -RETAIL_TRAP_THRESHOLD and fii["ce_net_short_chg"] < -FII_OPT_THRESHOLD:
            retail_confirmation_score = 5
            retail_confirmation_message = "RETAIL CALL CONFIRMATION: Retail not chasing rally as FIIs cover calls."
        elif client_pe_net_buy < -RETAIL_TRAP_THRESHOLD and fii["pe_net_short_chg"] < -FII_OPT_THRESHOLD:
            retail_confirmation_score = -5
            retail_confirmation_message = "RETAIL PUT CONFIRMATION: Retail reducing hedges while FIIs unwind put floor."

    score = max(
        -SCORE_CLIP,
        min(
            SCORE_CLIP,
            weighted_score + trap_adjustment + retail_confirmation_score + fii_dii_modifier + iv_modifier,
        ),
    )

    if score >= 40:
        bias_label = "HIGH CONFIDENCE BULLISH"
        action_desc = "FII (and, to a lesser extent, Pro/DII) desks are aggressively covering Call shorts and building Put floors."
    elif score >= 15:
        bias_label = "MODERATE BULLISH"
        action_desc = "Net positive institutional flows with mild Put short additions."
    elif score <= -40:
        bias_label = "HIGH CONFIDENCE BEARISH"
        action_desc = "FIIs are adding heavy Call shorts while unwinding Put support."
    elif score <= -15:
        bias_label = "MODERATE BEARISH"
        action_desc = "Operators are capping upside via Call writing."
    else:
        bias_label = "NEUTRAL / SIDEWAYS"
        action_desc = "Mixed operator signals — expecting rangebound consolidation."

    weighted_clipped_before_adjustments = float(weighted_score)

    # ── Build flat output dict ───────────────────────────────────────
    # Use a helper to save ~100 lines of repetitive key-value wiring.
    def _p_out(name: str, p: dict, raw_score: int) -> dict:
        return {
            f"{name}_fut_net_change": p["fut_chg"],
            f"{name}_fut_long_change": p["fut_long_chg"],
            f"{name}_fut_short_change": p["fut_short_chg"],
            f"{name}_ce_long_change": p["ce_long_chg"],
            f"{name}_ce_short_change": p["ce_short_chg"],
            f"{name}_ce_net_short_change": p["ce_net_short_chg"],
            f"{name}_pe_long_change": p["pe_long_chg"],
            f"{name}_pe_short_change": p["pe_short_chg"],
            f"{name}_pe_net_short_change": p["pe_net_short_chg"],
            f"{name}_raw_score": raw_score,
            f"{name}_stk_fut_net_change": p["stk_fut_chg"],
            f"{name}_stk_fut_long_change": p["stk_fut_long_chg"],
            f"{name}_stk_fut_short_change": p["stk_fut_short_chg"],
            f"{name}_stk_ce_net_change": p["stk_ce_short_chg"] - p["stk_ce_long_chg"],
            f"{name}_stk_pe_net_change": p["stk_pe_short_chg"] - p["stk_pe_long_chg"],
        }

    result: dict = {
        "date": latest_date,
        "prev_date": prev_date,
        "smart_money_score": score,
        "bias_label": bias_label,
        "action_desc": action_desc,
        "retail_trap_alarm": retail_trap_alarm,
        "trap_adjustment": trap_adjustment,
        "retail_confirmation_message": retail_confirmation_message,
        "retail_confirmation_score": retail_confirmation_score,
        "fii_dii_modifier": fii_dii_modifier,
        "iv_modifier_applied": iv_modifier,
        "weighted_clipped_before_adjustments": weighted_clipped_before_adjustments,
    }
    result.update(_p_out("fii", fii, fii_raw_score))
    result.update(_p_out("pro", pro, pro_raw_score))
    result.update(_p_out("dii", dii, dii_raw_score))

    # Client-specific
    result.update({
        "client_ce_net_buy": client_ce_net_buy,
        "client_pe_net_buy": client_pe_net_buy,
        "client_ce_long_change": client["ce_long_chg"],
        "client_ce_short_change": client["ce_short_chg"],
        "client_pe_long_change": client["pe_long_chg"],
        "client_pe_short_change": client["pe_short_chg"],
        "client_fut_net_change": client["fut_chg"],
        "client_fut_long_change": client["fut_long_chg"],
        "client_fut_short_change": client["fut_short_chg"],
        "client_stk_fut_net_change": client["stk_fut_chg"],
        "client_stk_fut_long_change": client["stk_fut_long_chg"],
        "client_stk_fut_short_change": client["stk_fut_short_chg"],
        "client_stk_ce_net_change": client["stk_ce_short_chg"] - client["stk_ce_long_chg"],
        "client_stk_pe_net_change": client["stk_pe_short_chg"] - client["stk_pe_long_chg"],
    })

    # Carried positions
    result.update({
        "fii_fut_net_carried": float(fii_today.get("Future Index Long", 0)) - float(fii_today.get("Future Index Short", 0)),
        "pro_fut_net_carried": float(pro_today.get("Future Index Long", 0)) - float(pro_today.get("Future Index Short", 0)),
        "dii_fut_net_carried": float(dii_today.get("Future Index Long", 0)) - float(dii_today.get("Future Index Short", 0)),
        "weights": {"fii": FII_WEIGHT, "pro": PRO_WEIGHT, "dii": DII_WEIGHT, "client": 0.0},
    })

    return result


def load_participant_data(iv_modifier: float = 0) -> dict | None:
    """Load latest FDCP data and derive FII, Pro & DII daily positioning shifts."""
    if not os.path.exists(FDCP_FILE):
        return None

    try:
        df = pd.read_csv(FDCP_FILE)
        df.columns = df.columns.str.strip()

        raw_dates = list(df["Date"].unique())
        dates = sort_dates_chronologically(raw_dates)

        if len(dates) < 2:
            latest_date = dates[-1] if len(dates) == 1 else None
            prev_date = None
        else:
            latest_date = dates[-1]
            prev_date = dates[-2]

        def get_row(p_type: str, d_str: str | None) -> dict:
            if not d_str:
                return {}
            sub = df[(df["Client Type"] == p_type) & (df["Date"] == d_str)]
            return sub.iloc[0].to_dict() if not sub.empty else {}

        return _score_date_pair(
            get_row("FII", latest_date), get_row("FII", prev_date),
            get_row("Pro", latest_date), get_row("Pro", prev_date),
            get_row("DII", latest_date), get_row("DII", prev_date),
            get_row("Client", latest_date), get_row("Client", prev_date),
            latest_date, prev_date, iv_modifier,
        )

    except Exception as e:
        print(f"Error parsing FDCP data: {e}")
        return None


def build_score_history(latest_summary: dict | None = None) -> list[dict]:
    """Per-date verdict score history from every FDCP date (oldest → newest).

    Historical dates have no archived option-chain IV, so `iv_modifier` is 0 for
    them; the newest entry is stamped from `latest_summary` (the live engine
    output) so the banner and the history can never disagree on today's score.
    """
    if not os.path.exists(FDCP_FILE):
        return []

    try:
        df = pd.read_csv(FDCP_FILE)
        df.columns = df.columns.str.strip()
        dates = sort_dates_chronologically(list(df["Date"].unique()))

        def get_row(p_type: str, d_str: str | None) -> dict:
            if not d_str:
                return {}
            sub = df[(df["Client Type"] == p_type) & (df["Date"] == d_str)]
            return sub.iloc[0].to_dict() if not sub.empty else {}

        history: list[dict] = []
        for i, d in enumerate(dates):
            prev = dates[i - 1] if i > 0 else None
            summary = _score_date_pair(
                get_row("FII", d), get_row("FII", prev),
                get_row("Pro", d), get_row("Pro", prev),
                get_row("DII", d), get_row("DII", prev),
                get_row("Client", d), get_row("Client", prev),
                d, prev, iv_modifier=0,
            )
            history.append({
                "date": d,
                "prev_date": prev,
                "score": summary["smart_money_score"],
                "bias": summary["bias_label"],
                "actionDesc": summary["action_desc"],
                "fiiRawScore": summary["fii_raw_score"],
                "proRawScore": summary["pro_raw_score"],
                "diiRawScore": summary["dii_raw_score"],
            })

        if latest_summary and history:
            history[-1].update({
                "score": latest_summary["smart_money_score"],
                "bias": latest_summary["bias_label"],
                "actionDesc": latest_summary["action_desc"],
                "fiiRawScore": latest_summary["fii_raw_score"],
                "proRawScore": latest_summary["pro_raw_score"],
                "diiRawScore": latest_summary["dii_raw_score"],
                "ivModifier": latest_summary.get("iv_modifier_applied", 0),
            })
        return history
    except Exception as e:
        print(f"[ENGINE] Error building score history: {e}")
        return []


def build_flat_changes_history(days: int = CHANGES_DAYS) -> dict:
    """Flat <field>_{today|Nd_ago} export for the last `days` FDCP dates.

    Reuses _score_date_pair per date pair — no scoring math duplicated here.
    """
    if not os.path.exists(FDCP_FILE) or days < 1:
        return {}
    try:
        df = pd.read_csv(FDCP_FILE)
        df.columns = df.columns.str.strip()
        dates = sort_dates_chronologically(list(df["Date"].unique()))

        def get_row(p_type: str, d_str: str | None) -> dict:
            if not d_str:
                return {}
            sub = df[(df["Client Type"] == p_type) & (df["Date"] == d_str)]
            return sub.iloc[0].to_dict() if not sub.empty else {}

        out: dict = {}
        for idx in range(days):
            sfx = "today" if idx == 0 else f"{idx}d_ago"
            i = len(dates) - 1 - idx
            d = dates[i] if i >= 0 else None
            prev = dates[i - 1] if i >= 1 else None
            out[f"date_{sfx}"] = d
            if d is None:
                continue
            summary = _score_date_pair(
                get_row("FII", d), get_row("FII", prev),
                get_row("Pro", d), get_row("Pro", prev),
                get_row("DII", d), get_row("DII", prev),
                get_row("Client", d), get_row("Client", prev),
                d, prev, iv_modifier=0,
            )
            for k in CHANGES_KEYS:
                out[f"{k}_{sfx}"] = summary.get(k)
        return out
    except Exception as e:
        print(f"[ENGINE] Error building changes history: {e}")
        return {}


# ── Index Roll Detection ───────────────────────────────────────────────────

def detect_index_rolls(stock_data: dict) -> dict:
    """
    Detects Resistance & Support Rolls, Magnet Strikes, Expected Expiry Ranges,
    and Operator Squeeze / Trap Alarms for all tracked indices.
    """
    results: dict = {}

    for symbol in INDICES:
        if symbol not in stock_data:
            continue

        raw = stock_data[symbol]
        ltp = raw.get("ltp")
        expiry = raw.get("expiry")
        strikes = raw.get("strikes", [])

        if not ltp or not strikes:
            continue

        strikes = sorted(strikes, key=lambda x: x["strike"])

        near = [s for s in strikes if abs(s["strike"] - ltp) / ltp <= 0.06]
        if not near:
            near = strikes

        strike_diffs = [near[i + 1]["strike"] - near[i]["strike"] for i in range(len(near) - 1)]
        step_size = float(np.median(strike_diffs)) if strike_diffs else 50.0
        if step_size <= 0:
            step_size = 50.0

        res_wall = max(near, key=lambda x: x["ce_oi"])["strike"]
        fresh_res = max(near, key=lambda x: x["ce_change_oi"])["strike"]
        unwind_res_obj = min(near, key=lambda x: x["ce_change_oi"])
        unwind_res = unwind_res_obj["strike"] if unwind_res_obj["ce_change_oi"] < -500 else None

        sup_wall = max(near, key=lambda x: x["pe_oi"])["strike"]
        fresh_sup = max(near, key=lambda x: x["pe_change_oi"])["strike"]
        unwind_sup_obj = min(near, key=lambda x: x["pe_change_oi"])
        unwind_sup = unwind_sup_obj["strike"] if unwind_sup_obj["pe_change_oi"] < -500 else None

        # Max Pain
        pain_map: dict = {}
        for target in near:
            tp = target["strike"]
            total_loss = 0.0
            for s in near:
                if target["strike"] > s["strike"]:
                    total_loss += (target["strike"] - s["strike"]) * s["pe_oi"]
                elif target["strike"] < s["strike"]:
                    total_loss += (s["strike"] - target["strike"]) * s["ce_oi"]
            pain_map[tp] = total_loss
        max_pain = min(pain_map, key=lambda k: pain_map[k]) if pain_map else ltp

        magnet_strike = round((max_pain * 0.5 + res_wall * 0.25 + sup_wall * 0.25) / step_size) * step_size
        expiry_min = round((min(sup_wall, max_pain) - step_size) / step_size) * step_size
        expiry_max = round((max(res_wall, max_pain) + step_size) / step_size) * step_size
        expiry_range_str = f"{int(expiry_min):,} – {int(expiry_max):,}"

        try:
            exp_date = datetime.strptime(expiry, "%d-%b-%Y") if expiry else datetime.now()
            dte = max(0, (exp_date - datetime.now()).days)
        except Exception:
            dte = 0

        dte_weight = 1.0 + (dte * 0.15)

        traps_and_squeezes: list[dict] = []

        avg_iv = float(np.mean([max(s.get("ce_iv", 15), 1) + max(s.get("pe_iv", 15), 1) for s in near])) / 2.0 if near else 15.0
        iv_multiplier = max(0.5, min(2.0, avg_iv / 15.0))
        trap_threshold = -5000 / iv_multiplier

        atm_strike = min(near, key=lambda x: abs(x["strike"] - ltp))
        atm_ce_ltp = atm_strike.get("ce_ltp", 0)
        atm_pe_ltp = atm_strike.get("pe_ltp", 0)

        if atm_ce_ltp > 0 and atm_pe_ltp > 0:
            syn_fut = atm_strike["strike"] + atm_ce_ltp - atm_pe_ltp
            premium = syn_fut - ltp
            if premium > 20:
                traps_and_squeezes.append({
                    "type": "SYN_BULL",
                    "strike": atm_strike["strike"],
                    "badge": "SYNTHETIC PREMIUM",
                    "desc": f"Synthetic futures (+{premium:.1f} pts). Operators are loading Calls / Shorting Puts.",
                })
            elif premium < -20:
                traps_and_squeezes.append({
                    "type": "SYN_BEAR",
                    "strike": atm_strike["strike"],
                    "badge": "SYNTHETIC DISCOUNT",
                    "desc": f"Synthetic futures ({premium:.1f} pts). Operators are shorting futures via spread Parity.",
                })

        for s in near:
            st = s["strike"]
            if abs(st - ltp) / ltp > 0.015:
                continue

            adj_ce_doi = s["ce_change_oi"] * dte_weight
            adj_pe_doi = s["pe_change_oi"] * dte_weight

            if ltp > st and adj_ce_doi < trap_threshold and s["ce_oi"] > 5000:
                traps_and_squeezes.append({
                    "type": "CALL_SQUEEZE",
                    "strike": st,
                    "badge": "CALL WRITER SQUEEZE",
                    "desc": f"Bears forced to cover CE at {st} as LTP ({ltp:,.1f}) crossed above.",
                })
            elif ltp < st and adj_pe_doi < trap_threshold and s["pe_oi"] > 5000:
                traps_and_squeezes.append({
                    "type": "PUT_TRAP",
                    "strike": st,
                    "badge": "PUT WRITER TRAP",
                    "desc": f"Bulls trapped at {st} PE as LTP ({ltp:,.1f}) broke below.",
                })

        if len(traps_and_squeezes) > 3:
            traps_and_squeezes = traps_and_squeezes[:3]

        # Resistance roll
        if unwind_res and fresh_res > unwind_res and unwind_res_obj["ce_change_oi"] < -2000:
            res_roll = f"RESISTANCE ROLLED UP (+{int(fresh_res - unwind_res)} pts)"
            res_roll_type = "BULLISH"
            res_roll_desc = f"Bears exited {unwind_res} CE ({unwind_res_obj['ce_change_oi']:,}) and shifted up to {fresh_res} CE."
        elif unwind_res and fresh_res < unwind_res and unwind_res_obj["ce_change_oi"] < -2000:
            res_roll = f"RESISTANCE ROLLED DOWN (-{int(unwind_res - fresh_res)} pts)"
            res_roll_type = "BEARISH"
            res_roll_desc = f"Bears tightened ceiling from {unwind_res} down to {fresh_res} CE."
        else:
            res_roll = "RESISTANCE STABLE"
            res_roll_type = "NEUTRAL"
            res_roll_desc = f"Primary ceiling holding firm at {res_wall} CE."

        # Support roll
        if unwind_sup and fresh_sup > unwind_sup and unwind_sup_obj["pe_change_oi"] < -2000:
            sup_roll = f"SUPPORT ROLLED UP (+{int(fresh_sup - unwind_sup)} pts)"
            sup_roll_type = "BULLISH"
            sup_roll_desc = f"Bulls raised floor from {unwind_sup} up to {fresh_sup} PE."
        elif unwind_sup and fresh_sup < unwind_sup and unwind_sup_obj["pe_change_oi"] < -2000:
            sup_roll = f"SUPPORT ROLLED DOWN (-{int(unwind_sup - fresh_sup)} pts)"
            sup_roll_type = "BEARISH"
            sup_roll_desc = f"Bulls abandoned {unwind_sup} PE and retreated down to {fresh_sup} PE."
        else:
            sup_roll = "SUPPORT STABLE"
            sup_roll_type = "NEUTRAL"
            sup_roll_desc = f"Primary floor holding firm at {sup_wall} PE."

        tot_ce_oi = sum(s["ce_oi"] for s in near)
        tot_pe_oi = sum(s["pe_oi"] for s in near)
        tot_ce_doi = sum(s["ce_change_oi"] for s in near)
        tot_pe_doi = sum(s["pe_change_oi"] for s in near)

        pcr_oi = (tot_pe_oi / tot_ce_oi) if tot_ce_oi > 0 else 1.0
        pcr_doi = (tot_pe_doi / tot_ce_doi) if tot_ce_doi > 0 else 1.0

        divergence = "NEUTRAL"
        if pcr_doi > 1.3 and ltp < max_pain:
            divergence = "BULLISH DIVERGENCE (Smart Money Buying Dip)"
        elif pcr_doi < 0.7 and ltp > max_pain:
            divergence = "BEARISH DIVERGENCE (Operators Capping Rally)"

        results[symbol] = {
            "ltp": ltp,
            "expiry": expiry,
            "max_pain": max_pain,
            "magnet_strike": magnet_strike,
            "expiry_range": expiry_range_str,
            "pcr_oi": pcr_oi,
            "pcr_doi": pcr_doi,
            "divergence": divergence,
            "resistance_wall": res_wall,
            "fresh_resistance": fresh_res,
            "support_wall": sup_wall,
            "fresh_support": fresh_sup,
            "resistance_roll": res_roll,
            "resistance_roll_type": res_roll_type,
            "resistance_roll_desc": res_roll_desc,
            "support_roll": sup_roll,
            "support_roll_type": sup_roll_type,
            "support_roll_desc": sup_roll_desc,
            "traps_and_squeezes": traps_and_squeezes,
        }

    return results


# ── Stock Breadth Scan ─────────────────────────────────────────────────────

def scan_stock_breadth(stock_data: dict, participant_summary: dict | None = None) -> dict:
    """
    Scans all stocks in option chain data to find top 10 market leaders in:
    1. Fresh Call Writing (Operators Capping Upside → Bearish Stocks)
    2. Fresh Put Writing (Operators Defending Floor → Bullish Stocks)
    3. Call Unwinding (Short Squeeze Risk → Bullish Breakout Stocks)
    4. Put Unwinding (Floor Breakdown Risk → Bearish Stocks)
    """
    call_writing: list[dict] = []
    put_writing: list[dict] = []
    call_unwinding: list[dict] = []
    put_unwinding: list[dict] = []

    for sym, data in stock_data.items():
        ltp = data.get("ltp")
        strikes = data.get("strikes", [])
        if not ltp or not strikes:
            continue

        net_ce_doi = sum(s["ce_change_oi"] for s in strikes)
        net_pe_doi = sum(s["pe_change_oi"] for s in strikes)
        net_ce_oi = sum(s["ce_oi"] for s in strikes)
        net_pe_oi = sum(s["pe_oi"] for s in strikes)

        top_ce_write = max(strikes, key=lambda s: s["ce_change_oi"])
        top_pe_write = max(strikes, key=lambda s: s["pe_change_oi"])
        top_ce_unwind = min(strikes, key=lambda s: s["ce_change_oi"])
        top_pe_unwind = min(strikes, key=lambda s: s["pe_change_oi"])

        stock_summary: dict = {
            "symbol": sym,
            "ltp": ltp,
            "net_ce_doi": net_ce_doi,
            "net_pe_doi": net_pe_doi,
            "top_ce_write_strike": top_ce_write["strike"],
            "top_ce_write_doi": top_ce_write["ce_change_oi"],
            "top_pe_write_strike": top_pe_write["strike"],
            "top_pe_write_doi": top_pe_write["pe_change_oi"],
            "top_ce_unwind_strike": top_ce_unwind["strike"],
            "top_ce_unwind_doi": top_ce_unwind["ce_change_oi"],
            "top_pe_unwind_strike": top_pe_unwind["strike"],
            "top_pe_unwind_doi": top_pe_unwind["pe_change_oi"],
        }

        ce_threshold = max(500, net_ce_oi * 0.05) if net_ce_oi > 0 else 500
        pe_threshold = max(500, net_pe_oi * 0.05) if net_pe_oi > 0 else 500

        # Smart Money Breadth Alignment
        alignment = "NEUTRAL"
        if participant_summary:
            fii_ce_short = participant_summary.get("fii_ce_net_short_change", 0)
            fii_pe_short = participant_summary.get("fii_pe_net_short_change", 0)
            fii_call_bearish = fii_ce_short > FII_OPT_THRESHOLD
            fii_call_bullish = fii_ce_short < -FII_OPT_THRESHOLD
            fii_put_bullish = fii_pe_short > FII_OPT_THRESHOLD
            fii_put_bearish = fii_pe_short < -FII_OPT_THRESHOLD

            if (net_ce_doi > ce_threshold and fii_call_bearish) \
                    or (net_ce_doi < -ce_threshold and fii_call_bullish) \
                    or (net_pe_doi > pe_threshold and fii_put_bullish) \
                    or (net_pe_doi < -pe_threshold and fii_put_bearish):
                alignment = "ALIGNED"
            elif (net_ce_doi > ce_threshold and fii_call_bullish) \
                    or (net_pe_doi > pe_threshold and fii_put_bearish) \
                    or (net_ce_doi < -ce_threshold and fii_call_bearish) \
                    or (net_pe_doi < -pe_threshold and fii_put_bullish):
                alignment = "OPPOSED"

        stock_summary["alignment"] = alignment

        if net_ce_doi > ce_threshold:
            call_writing.append(stock_summary)
        elif net_ce_doi < -ce_threshold:
            call_unwinding.append(stock_summary)

        if net_pe_doi > pe_threshold:
            put_writing.append(stock_summary)
        elif net_pe_doi < -pe_threshold:
            put_unwinding.append(stock_summary)

    return {
        "call_writing_bearish": sorted(call_writing, key=lambda x: x["net_ce_doi"], reverse=True)[:10],
        "put_writing_bullish": sorted(put_writing, key=lambda x: x["net_pe_doi"], reverse=True)[:10],
        "call_unwinding_bullish": sorted(call_unwinding, key=lambda x: x["net_ce_doi"])[:10],
        "put_unwinding_bearish": sorted(put_unwinding, key=lambda x: x["net_pe_doi"])[:10],
        "counts": {
            "call_writing": len(call_writing),
            "put_writing": len(put_writing),
            "call_unwinding": len(call_unwinding),
            "put_unwinding": len(put_unwinding),
        },
    }


# ── Flow Divergence ─────────────────────────────────────────────────────────

def detect_flow_divergence(stock_data: dict, participant_summary: dict | None) -> list[dict]:
    """
    Identifies strikes where institutional flow and strike OI movement diverge,
    signalling potential traps, squeezes, or conflicting battles.
    Thresholds are scaled per index relative to NIFTY OI baseline.
    """
    divergences: list[dict] = []
    if not participant_summary:
        return divergences

    fii_ce_short = participant_summary.get("fii_ce_net_short_change", 0)
    fii_pe_short = participant_summary.get("fii_pe_net_short_change", 0)

    # First pass: compute per-index average OI for threshold scaling
    index_avg_oi: dict[str, float] = {}
    for sym in INDICES:
        if sym not in stock_data:
            continue
        raw = stock_data[sym]
        ltp = raw.get("ltp")
        strikes = raw.get("strikes", [])
        if not ltp or not strikes:
            continue
        strikes = sorted(strikes, key=lambda x: x["strike"])
        near = [s for s in strikes if abs(s["strike"] - ltp) / ltp <= 0.04]
        oi_vals = [s.get("ce_oi", 0) for s in near if s.get("ce_oi", 0) > 0]
        index_avg_oi[sym] = float(np.mean(oi_vals)) if oi_vals else 1.0

    ref_avg_oi = index_avg_oi.get("NIFTY", 1.0)

    # Second pass: detect divergences with scaled thresholds
    for sym in INDICES:
        if sym not in stock_data:
            continue
        raw = stock_data[sym]
        ltp = raw.get("ltp")
        strikes = raw.get("strikes", [])
        if not ltp or not strikes:
            continue
        strikes = sorted(strikes, key=lambda x: x["strike"])
        near = [s for s in strikes if abs(s["strike"] - ltp) / ltp <= 0.04]

        avg_oi = index_avg_oi.get(sym, 1.0)
        scale = avg_oi / ref_avg_oi if ref_avg_oi > 0 else 1.0
        conflict_th = int(5000 * scale)
        unwind_th = int(5000 * scale)
        resistance_th = int(8000 * scale)
        floor_th = int(5000 * scale)

        for s in near:
            st = s["strike"]
            ce_doi = s.get("ce_change_oi", 0)
            pe_doi = s.get("pe_change_oi", 0)

            # Conflict: Both CE and PE building at same strike
            if ce_doi > conflict_th and pe_doi > conflict_th:
                divergences.append({
                    "symbol": sym,
                    "strike": st,
                    "type": "CONFLICT_ZONE",
                    "signal": "CE + PE both building",
                    "desc": f"Both Calls (+{ce_doi:,}) and Puts (+{pe_doi:,}) building at {st}. Major battle zone — expect high volatility.",
                })
                continue

            # FII writing calls (bearish macro) but CE unwinding here (bullish at this strike)
            if fii_ce_short > FII_OPT_THRESHOLD and ce_doi < -unwind_th:
                divergences.append({
                    "symbol": sym,
                    "strike": st,
                    "type": "BULLISH_DIVERGENCE",
                    "signal": "FII bearish but CE unwinding",
                    "desc": f"FII writing calls ({fii_ce_short:,.0f}) yet CE unwinding at {st} ({ce_doi:,}). Local short squeeze — opposes macro view.",
                })
                continue

            # FII writing puts (bullish macro) but PE unwinding here (bearish at this strike)
            if fii_pe_short > FII_OPT_THRESHOLD and pe_doi < -unwind_th:
                divergences.append({
                    "symbol": sym,
                    "strike": st,
                    "type": "BEARISH_DIVERGENCE",
                    "signal": "FII bullish but PE unwinding",
                    "desc": f"FII writing puts ({fii_pe_short:,.0f}) yet PE unwinding at {st} ({pe_doi:,}). Local floor breakdown — opposes macro view.",
                })
                continue

            # Price above strike but CE building
            if ltp > st and ce_doi > resistance_th:
                divergences.append({
                    "symbol": sym,
                    "strike": st,
                    "type": "RESISTANCE_BUILDING",
                    "signal": "Price above yet CE building",
                    "desc": f"LTP {ltp:,.1f} > {st} but CE OI building (+{ce_doi:,}). Smart money adding resistance above — rally cap imminent?",
                })
                continue

            # Price below strike but PE unwinding
            if ltp < st and pe_doi < -floor_th:
                divergences.append({
                    "symbol": sym,
                    "strike": st,
                    "type": "FLOOR_WEAKENING",
                    "signal": "Price below yet PE unwinding",
                    "desc": f"LTP {ltp:,.1f} < {st} but PE unwinding ({pe_doi:,}). Support below price fading — further downside risk.",
                })
                continue

    return divergences[:8]


# ── Flow attribution helpers ────────────────────────────────────────────────

def _attribute_ce_flow(ce_doi: float, fii_ce_short: float, client_ce_buy: float) -> str:
    if ce_doi > 5000 and fii_ce_short > FII_OPT_THRESHOLD:
        return "FII WRITING"
    elif ce_doi > 5000 and client_ce_buy > RETAIL_TRAP_THRESHOLD:
        return "RETAIL BUYING"
    elif ce_doi > 5000:
        return "WRITING"
    elif ce_doi < -5000:
        return "COVERING"
    return "--"


def _attribute_pe_flow(pe_doi: float, fii_pe_short: float, client_pe_buy: float) -> str:
    if pe_doi > 5000 and fii_pe_short > FII_OPT_THRESHOLD:
        return "FII FLOOR"
    elif pe_doi > 5000 and client_pe_buy > RETAIL_TRAP_THRESHOLD:
        return "RETAIL HEDGING"
    elif pe_doi > 5000:
        return "WRITING"
    elif pe_doi < -5000:
        return "UNWINDING"
    return "--"


# ── Multi-Day Conviction ────────────────────────────────────────────────────

def build_multiday_conviction(history_dir: str, participant_summary: dict | None = None) -> dict:
    """
    Reads archived daily OC JSON files from docs/oc_history/
    to compute multi-day strike conviction trends for NIFTY and BANKNIFTY.
    """
    cleanup_old_history(history_dir, max_days=30)

    files = sorted(glob.glob(os.path.join(history_dir, "*.json")))
    if not files:
        return {}

    recent_files = files[-5:]
    dates = [os.path.basename(f).replace(".json", "") for f in recent_files]

    conviction: dict = {}
    ref_avg_oi: float | None = None

    for sym in ["NIFTY", "BANKNIFTY"]:
        multiday_map: dict[float, dict] = {}

        latest_ltp: float | None = None
        for f_path in reversed(recent_files):
            try:
                with open(f_path) as f:
                    snap = json.load(f)
                latest_ltp = snap.get("stocks", {}).get(sym, {}).get("ltp")
                if latest_ltp:
                    break
            except Exception:
                continue

        for f_path in recent_files:
            try:
                with open(f_path) as f:
                    snap = json.load(f)
                s_data = snap.get("stocks", {}).get(sym, {})
                ltp = s_data.get("ltp")
                strikes = s_data.get("strikes", [])

                if not ltp or not strikes:
                    continue

                for s in strikes:
                    st = s["strike"]
                    if abs(st - ltp) / ltp > 0.04:
                        continue

                    if st not in multiday_map:
                        multiday_map[st] = {
                            "strike": st,
                            "ce_oi_history": [],
                            "pe_oi_history": [],
                            "today_ce_doi": s.get("ce_change_oi", 0),
                            "today_pe_doi": s.get("pe_change_oi", 0),
                        }

                    multiday_map[st]["ce_oi_history"].append(s["ce_oi"])
                    multiday_map[st]["pe_oi_history"].append(s["pe_oi"])
            except Exception:
                continue

        all_strikes = list(multiday_map.values())
        if latest_ltp and all_strikes:
            all_strikes = sorted(all_strikes, key=lambda x: abs(x["strike"] - latest_ltp))[:15]
            sorted_strikes = sorted(all_strikes, key=lambda x: x["strike"])
        else:
            sorted_strikes = sorted(all_strikes, key=lambda x: x["strike"])[:15]

        # Compute average OI for threshold scaling
        avg_ce_oi = 0.0
        oi_vals = [item["ce_oi_history"][-1] for item in sorted_strikes if item["ce_oi_history"]]
        if oi_vals:
            avg_ce_oi = sum(oi_vals) / len(oi_vals)

        if sym == "NIFTY" and avg_ce_oi > 0:
            ref_avg_oi = avg_ce_oi
        scale = 1.0
        if ref_avg_oi and avg_ce_oi > 0 and sym != "NIFTY":
            scale = avg_ce_oi / ref_avg_oi

        hard_res_th = int(25000 * scale)
        building_th = int(2500 * scale)
        unwind_th = int(1500 * scale)

        for item in sorted_strikes:
            ce_hist = item["ce_oi_history"]
            pe_hist = item["pe_oi_history"]

            if len(ce_hist) >= 2:
                ce_diff = ce_hist[-1] - ce_hist[0]
            else:
                ce_diff = item.get("today_ce_doi", 0)

            item["ce_trend_delta"] = ce_diff
            if ce_diff > hard_res_th:
                item["ce_conviction"] = "HARD RESISTANCE"
            elif ce_diff > building_th:
                item["ce_conviction"] = "CE BUILDING"
            elif ce_diff < -unwind_th:
                item["ce_conviction"] = "CE UNWINDING"
            else:
                item["ce_conviction"] = "STABLE"

            if len(pe_hist) >= 2:
                pe_diff = pe_hist[-1] - pe_hist[0]
            else:
                pe_diff = item.get("today_pe_doi", 0)

            item["pe_trend_delta"] = pe_diff
            if pe_diff > hard_res_th:
                item["pe_conviction"] = "SOLID FLOOR"
            elif pe_diff > building_th:
                item["pe_conviction"] = "PE BUILDING"
            elif pe_diff < -unwind_th:
                item["pe_conviction"] = "PE UNWINDING"
            else:
                item["pe_conviction"] = "STABLE"

            # Flow alignment and attribution
            if participant_summary:
                fii_ce_short = participant_summary.get("fii_ce_net_short_change", 0)
                fii_pe_short = participant_summary.get("fii_pe_net_short_change", 0)
                client_ce_buy = participant_summary.get("client_ce_net_buy", 0)
                client_pe_buy = participant_summary.get("client_pe_net_buy", 0)

                fii_call_bearish = fii_ce_short > FII_OPT_THRESHOLD
                fii_call_bullish = fii_ce_short < -FII_OPT_THRESHOLD
                fii_put_bullish = fii_pe_short > FII_OPT_THRESHOLD
                fii_put_bearish = fii_pe_short < -FII_OPT_THRESHOLD

                # CE alignment
                if (fii_call_bearish and ce_diff > building_th) or (fii_call_bullish and ce_diff < -unwind_th):
                    item["ce_alignment"] = "ALIGNED"
                elif (fii_call_bullish and ce_diff > building_th) or (fii_call_bearish and ce_diff < -unwind_th):
                    item["ce_alignment"] = "OPPOSED"
                else:
                    item["ce_alignment"] = "NEUTRAL"

                # PE alignment
                if (fii_put_bullish and pe_diff > building_th) or (fii_put_bearish and pe_diff < -unwind_th):
                    item["pe_alignment"] = "ALIGNED"
                elif (fii_put_bearish and pe_diff > building_th) or (fii_put_bullish and pe_diff < -unwind_th):
                    item["pe_alignment"] = "OPPOSED"
                else:
                    item["pe_alignment"] = "NEUTRAL"

                item["ce_flow_attr"] = _attribute_ce_flow(ce_diff, fii_ce_short, client_ce_buy)
                item["pe_flow_attr"] = _attribute_pe_flow(pe_diff, fii_pe_short, client_pe_buy)
            else:
                item["ce_alignment"] = "NEUTRAL"
                item["pe_alignment"] = "NEUTRAL"
                item["ce_flow_attr"] = "--"
                item["pe_flow_attr"] = "--"

        conviction[sym] = {"dates": dates, "strikes": sorted_strikes}

    return conviction


# ── Master runner ───────────────────────────────────────────────────────────

def _nested_summary(ps: dict) -> dict:
    """Map flat participant_summary → nested verdict/participants/retail.

    Flat participant_summary is kept in the payload untouched for telegram.py;
    this nested view is what the new dashboard consumes.
    """
    parts = {}
    for name, pref in {"fii": "fii", "pro": "pro", "dii": "dii"}.items():
        parts[name] = {
            "futures": {
                "net": ps.get(f"{pref}_fut_net_change", 0),
                "long": ps.get(f"{pref}_fut_long_change", 0),
                "short": ps.get(f"{pref}_fut_short_change", 0),
                "stockNet": ps.get(f"{pref}_stk_fut_net_change", 0),
                "stockLong": ps.get(f"{pref}_stk_fut_long_change", 0),
                "stockShort": ps.get(f"{pref}_stk_fut_short_change", 0),
                "netCarried": ps.get(f"{pref}_fut_net_carried", 0),
            },
            "options": {
                "ce": {
                    "long": ps.get(f"{pref}_ce_long_change", 0),
                    "short": ps.get(f"{pref}_ce_short_change", 0),
                    "netShort": ps.get(f"{pref}_ce_net_short_change", 0),
                },
                "pe": {
                    "long": ps.get(f"{pref}_pe_long_change", 0),
                    "short": ps.get(f"{pref}_pe_short_change", 0),
                    "netShort": ps.get(f"{pref}_pe_net_short_change", 0),
                },
                "stkCeNet": ps.get(f"{pref}_stk_ce_net_change", 0),
                "stkPeNet": ps.get(f"{pref}_stk_pe_net_change", 0),
            },
            "rawScore": ps.get(f"{pref}_raw_score", 0),
        }
    parts["client"] = {
        "futures": {
            "net": ps.get("client_fut_net_change", 0),
            "long": ps.get("client_fut_long_change", 0),
            "short": ps.get("client_fut_short_change", 0),
            "stockNet": ps.get("client_stk_fut_net_change", 0),
            "stockLong": ps.get("client_stk_fut_long_change", 0),
            "stockShort": ps.get("client_stk_fut_short_change", 0),
            "netCarried": ps.get("client_fut_net_carried", 0),  # ponytail: no client carried source key — 0 default; wire if computed
        },
        "options": {
            "ce": {"long": ps.get("client_ce_long_change", 0),
                   "short": ps.get("client_ce_short_change", 0),
                   "netBuy": ps.get("client_ce_net_buy", 0)},
            "pe": {"long": ps.get("client_pe_long_change", 0),
                   "short": ps.get("client_pe_short_change", 0),
                   "netBuy": ps.get("client_pe_net_buy", 0)},
            "stkCeNet": ps.get("client_stk_ce_net_change", 0),
            "stkPeNet": ps.get("client_stk_pe_net_change", 0),
        },
    }
    return {
        "verdict": {
            "score": ps.get("smart_money_score", 0),
            "bias": ps.get("bias_label", "NEUTRAL"),
            "actionDesc": ps.get("action_desc", ""),
            "scoreBreakdown": ps.get("weights", {}),
        },
        "participants": parts,
        "retail": {
            "trapAlarm": ps.get("retail_trap_alarm"),
            "confirmationMessage": ps.get("retail_confirmation_message"),
            "confirmationScore": ps.get("retail_confirmation_score", 0),
            "adjustment": ps.get("trap_adjustment", 0),
        },
        "weights": ps.get("weights", {}),
    }


def run_engine():
    """Master runner: FDCP + Option Chain + Archives → money_flow_data.json."""
    print("[ENGINE] Running Institutional Verdict Engine...")

    if not os.path.exists(NSE_DATA_FILE):
        print(f"[ENGINE] Error: {NSE_DATA_FILE} not found. Run OC fetch first.")
        return

    with open(NSE_DATA_FILE) as f:
        oc_raw = json.load(f)

    timestamp = oc_raw.get("timestamp", datetime.now(timezone.utc).isoformat())
    stocks = oc_raw.get("stocks", {})

    participant_summary = load_participant_data(iv_modifier=compute_iv_modifier(stocks))
    index_rolls = detect_index_rolls(stocks)
    stock_breadth = scan_stock_breadth(stocks, participant_summary)
    conviction_trends = build_multiday_conviction(HISTORY_DIR, participant_summary)
    flow_divergence = detect_flow_divergence(stocks, participant_summary)

    score_breakdown: dict = {}
    if participant_summary:
        score_breakdown = {
            "fii_raw_score": participant_summary.get("fii_raw_score", 0),
            "pro_raw_score": participant_summary.get("pro_raw_score", 0),
            "dii_raw_score": participant_summary.get("dii_raw_score", 0),
            "fii_weight": FII_WEIGHT,
            "pro_weight": PRO_WEIGHT,
            "dii_weight": DII_WEIGHT,
            "weighted_clipped_before_adjustments": participant_summary.get("weighted_clipped_before_adjustments", 0),
            "trap_adjustment": participant_summary.get("trap_adjustment", 0),
            "retail_confirmation_score": participant_summary.get("retail_confirmation_score", 0),
            "fii_dii_modifier": participant_summary.get("fii_dii_modifier", 0),
            "iv_modifier": participant_summary.get("iv_modifier_applied", 0),
        }

    nested = _nested_summary(participant_summary) if participant_summary else {
        "verdict": {"score": 0, "bias": "NEUTRAL", "actionDesc": ""},
        "participants": {}, "retail": {}, "weights": {},
    }
    verdict_payload = {
        "timestamp": timestamp,
        "executive_summary": {
            "bias_label": participant_summary["bias_label"] if participant_summary else "NEUTRAL",
            "smart_money_score": participant_summary["smart_money_score"] if participant_summary else 0,
            "action_desc": participant_summary["action_desc"] if participant_summary else "No participant data available.",
            "score_breakdown": score_breakdown,
        },
        "participant_summary": participant_summary,   # kept flat — telegram.py reads this
        "score_history": build_score_history(participant_summary),  # per-date verdict history — dashboard date nav
        "verdict": nested["verdict"],
        "participants": nested["participants"],
        "retail": nested["retail"],
        "weights": nested["weights"],
        "rolls": index_rolls,
        "breadth": stock_breadth,
        "conviction": conviction_trends,
        "divergence": flow_divergence,
        "stock_count": len(stocks),
    }

    # Clean numpy/pandas types for JSON
    cleaned = clean_val(verdict_payload)

    with open(OUTPUT_FILE, "w") as f:
        json.dump(cleaned, f, indent=2)

    # Flat change-fields snapshot → separate JSON (written every engine run)
    changes_payload = {"timestamp": timestamp, **build_flat_changes_history()}
    with open(CHANGES_FILE, "w") as f:
        json.dump(clean_val(changes_payload), f, indent=2)

    print(f"[ENGINE] OK! Saved to {OUTPUT_FILE}")
    print(f"[ENGINE] Changes snapshot saved to {CHANGES_FILE}")
    print(f"   Bias: {verdict_payload['executive_summary']['bias_label']}")
    print(f"   Index Rolls: {list(index_rolls.keys())}")
    print(f"   Stock Breadth: Call Write={len(stock_breadth['call_writing_bearish'])}, Put Write={len(stock_breadth['put_writing_bullish'])}")
    print(f"   Flow Divergences: {len(flow_divergence)}")
