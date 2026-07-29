"""
Money Flow & Institutional Verdict Engine
------------------------------------------
Cross-correlates Gross Participant OI (FDCP_Data.csv) with Strike-Level Option Chains (nse_data.json)
and multi-day snapshot archives (docs/oc_history/) to deliver institutional verdicts.

Verdict Categories:
1. Executive Market Verdict (Bullish / Bearish / Sideways + Confidence Score)
2. Participant Options Stance (FII / Pro / DII Call/Put Long & Short additions/reductions from FDCP)
3. Index Roll Intelligence (Resistance & Support Roll direction & magnitude)
4. Stock F&O Breadth (Top Call/Put writing & unwinding stocks across all 215 symbols)
5. Multi-Day Strike Conviction Heatmap (Indices & major stocks)

Participant weighting philosophy (explicit, by design):
    FII  weight = 1.00  (largest, most informationally significant flows)
    Pro  weight = 0.60  (prop desks / arbitrageurs - meaningful but often hedge-driven)
    DII  weight = 0.40  (mutual funds/insurers - slower-moving, still directional signal)
    Client (retail) is NEVER scored directly. It is only used as a contrarian
    overlay ("trapped retail") that nudges the score when retail is heavily
    positioned against what FII is doing - i.e. the lowest-priority participant
    only matters in how it confirms/contradicts the higher-priority ones.
"""

import json
import os
import glob
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta

FDCP_FILE = "FDCP_Data.csv"
NSE_DATA_FILE = os.path.join("docs", "nse_data.json")
HISTORY_DIR = os.path.join("docs", "oc_history")
OUTPUT_FILE = os.path.join("docs", "money_flow_data.json")

# Explicit participant weights (FII > Pro > DII > Client). Client is excluded
# on purpose - see module docstring.
FII_WEIGHT = 1.00
PRO_WEIGHT = 0.60
DII_WEIGHT = 0.40

# Score thresholds — FII baseline, Pro (0.6x), DII (0.4x)
FII_FUT_THRESHOLD = 5000
FII_OPT_THRESHOLD = 10000
PRO_FUT_THRESHOLD = 3000
PRO_OPT_THRESHOLD = 6000
DII_FUT_THRESHOLD = 2000
DII_OPT_THRESHOLD = 4000
RETAIL_TRAP_THRESHOLD = 25000

# Composite score is clipped to this range both before and after the retail-trap overlay
SCORE_CLIP = 100


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


def _sort_dates_chronologically(raw_dates):
    """
    df['Date'].unique() preserves first-appearance order in the CSV, NOT
    chronological order. If the file is ever appended out of sequence (or
    re-sorted / reloaded), 'latest' and 'previous' silently swap.
    This parses each date string and sorts properly, falling back to the
    original string order only if parsing fails entirely.
    """
    try:
        parsed = pd.to_datetime(pd.Series(raw_dates), dayfirst=True, errors="coerce")
        if parsed.isna().any():
            # Mixed/unparseable formats - fall back to raw order rather than guessing
            return list(raw_dates)
        order = parsed.sort_values().index
        return [raw_dates[i] for i in order]
    except Exception:
        return list(raw_dates)


def load_participant_data():
    """Load latest FDCP data and derive FII, Pro & DII daily positioning shifts."""
    if not os.path.exists(FDCP_FILE):
        return None

    try:
        df = pd.read_csv(FDCP_FILE)
        df.columns = df.columns.str.strip()

        raw_dates = list(df['Date'].unique())
        dates = _sort_dates_chronologically(raw_dates)

        if len(dates) < 2:
            latest_date = dates[-1] if len(dates) == 1 else None
            prev_date = None
        else:
            latest_date = dates[-1]
            prev_date = dates[-2]

        def get_row(p_type, d_str):
            if not d_str:
                return {}
            sub = df[(df['Client Type'] == p_type) & (df['Date'] == d_str)]
            return sub.iloc[0].to_dict() if not sub.empty else {}

        fii_today = get_row('FII', latest_date)
        fii_prev = get_row('FII', prev_date)
        pro_today = get_row('Pro', latest_date)
        pro_prev = get_row('Pro', prev_date)
        dii_today = get_row('DII', latest_date)
        dii_prev = get_row('DII', prev_date)
        client_today = get_row('Client', latest_date)
        client_prev = get_row('Client', prev_date)

        def calc_chg(row_t, row_p, col):
            return float(row_t.get(col, 0)) - float(row_p.get(col, 0)) if row_t and row_p else 0.0

        def load_participant_changes(row_t, row_p):
            """
            Returns net directional changes for one participant:
            fut_chg          : net index futures change (long - short delta)
            ce_net_short_chg : net CALL writing pressure  (short_chg - long_chg); +ve = capping upside
            pe_net_short_chg : net PUT writing pressure   (short_chg - long_chg); +ve = defending floor
            Long and short legs are ALWAYS netted together before anything downstream
            uses them - a participant adding both long and short calls at once should
            not register as pure directional writing.
            """
            fut_chg = calc_chg(row_t, row_p, 'Future Index Long') - calc_chg(row_t, row_p, 'Future Index Short')
            ce_long_chg = calc_chg(row_t, row_p, 'Option Index Call Long')
            ce_short_chg = calc_chg(row_t, row_p, 'Option Index Call Short')
            pe_long_chg = calc_chg(row_t, row_p, 'Option Index Put Long')
            pe_short_chg = calc_chg(row_t, row_p, 'Option Index Put Short')
            return {
                "fut_chg": fut_chg,
                "ce_long_chg": ce_long_chg,
                "ce_short_chg": ce_short_chg,
                "pe_long_chg": pe_long_chg,
                "pe_short_chg": pe_short_chg,
                "ce_net_short_chg": ce_short_chg - ce_long_chg,
                "pe_net_short_chg": pe_short_chg - pe_long_chg,
            }

        fii = load_participant_changes(fii_today, fii_prev)
        pro = load_participant_changes(pro_today, pro_prev)
        dii = load_participant_changes(dii_today, dii_prev)
        client = load_participant_changes(client_today, client_prev)

        # Client (Retail) net buy figures - used ONLY for the contrarian trap overlay,
        # never scored directly.
        client_ce_net_buy = client["ce_long_chg"] - client["ce_short_chg"]
        client_pe_net_buy = client["pe_long_chg"] - client["pe_short_chg"]

        def participant_score(p, fut_th, opt_th):
            """
            Proportional scoring: base ±15 for crossing threshold, plus up to ±10
            proportional to how far beyond the threshold. Max ±25 per leg.
            Positive = net bullish (buying futures, covering calls, writing puts).
            Negative = net bearish (selling futures, writing calls, unwinding puts).
            """
            s = 0

            # Futures
            if p["fut_chg"] > fut_th:
                ratio = min(1.0, (p["fut_chg"] - fut_th) / fut_th)
                s += 15 + round(ratio * 10)
            elif p["fut_chg"] < -fut_th:
                ratio = min(1.0, (abs(p["fut_chg"]) - fut_th) / fut_th)
                s -= 15 + round(ratio * 10)

            # Call options — negative = covering (bullish), positive = writing (bearish)
            if p["ce_net_short_chg"] < -opt_th:
                ratio = min(1.0, (abs(p["ce_net_short_chg"]) - opt_th) / opt_th)
                s += 15 + round(ratio * 10)
            elif p["ce_net_short_chg"] > opt_th:
                ratio = min(1.0, (p["ce_net_short_chg"] - opt_th) / opt_th)
                s -= 15 + round(ratio * 10)

            # Put options — positive = writing floor (bullish), negative = unwinding (bearish)
            if p["pe_net_short_chg"] > opt_th:
                ratio = min(1.0, (p["pe_net_short_chg"] - opt_th) / opt_th)
                s += 15 + round(ratio * 10)
            elif p["pe_net_short_chg"] < -opt_th:
                ratio = min(1.0, (abs(p["pe_net_short_chg"]) - opt_th) / opt_th)
                s -= 15 + round(ratio * 10)

            return max(-25, min(25, s))

        fii_raw_score = participant_score(fii, FII_FUT_THRESHOLD, FII_OPT_THRESHOLD)
        pro_raw_score = participant_score(pro, PRO_FUT_THRESHOLD, PRO_OPT_THRESHOLD)
        dii_raw_score = participant_score(dii, DII_FUT_THRESHOLD, DII_OPT_THRESHOLD)

        # Explicit weighted composite: FII > Pro > DII. Client excluded by design.
        weighted_score = (
            fii_raw_score * FII_WEIGHT
            + pro_raw_score * PRO_WEIGHT
            + dii_raw_score * DII_WEIGHT
        )
        weighted_score = max(-SCORE_CLIP, min(SCORE_CLIP, weighted_score))

        # Retail Trap / Contrarian Sentiment Filter (lowest-priority participant,
        # only ever nudges the already-weighted institutional score)
        retail_trap_alarm = None
        trap_adjustment = 0
        if client_ce_net_buy > RETAIL_TRAP_THRESHOLD and fii["ce_net_short_chg"] > FII_OPT_THRESHOLD:
            trap_adjustment = -15
            retail_trap_alarm = "RETAIL CALL TRAP ALERT: Retail buying calls while FIIs aggressively write calls."
        elif client_pe_net_buy > RETAIL_TRAP_THRESHOLD and fii["pe_net_short_chg"] > FII_OPT_THRESHOLD:
            # Retail is net LONG puts (bearish/hedging) while FII is writing puts
            # (defending the floor, i.e. bullish) - retail is on the wrong side.
            trap_adjustment = 15
            retail_trap_alarm = "RETAIL PUT TRAP ALERT: Retail buying puts while FIIs aggressively write puts."

        score = max(-SCORE_CLIP, min(SCORE_CLIP, weighted_score + trap_adjustment))

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

        # Track the clipped weighted score *before* trap adjustment so
        # score_breakdown.trap_adjustment is accurate (not conflated with clipping).
        # weighted_score is already clipped at this point.
        weighted_clipped_before_trap = weighted_score

        return {
            "date": latest_date,
            "prev_date": prev_date,
            "smart_money_score": score,
            "bias_label": bias_label,
            "action_desc": action_desc,
            "retail_trap_alarm": retail_trap_alarm,
            "trap_adjustment": trap_adjustment,
            "weighted_clipped_before_trap": weighted_clipped_before_trap,

            "fii_fut_net_change": fii["fut_chg"],
            "fii_ce_long_change": fii["ce_long_chg"],
            "fii_ce_short_change": fii["ce_short_chg"],
            "fii_ce_net_short_change": fii["ce_net_short_chg"],
            "fii_pe_long_change": fii["pe_long_chg"],
            "fii_pe_short_change": fii["pe_short_chg"],
            "fii_pe_net_short_change": fii["pe_net_short_chg"],
            "fii_raw_score": fii_raw_score,

            "pro_fut_net_change": pro["fut_chg"],
            "pro_ce_long_change": pro["ce_long_chg"],
            "pro_ce_short_change": pro["ce_short_chg"],
            "pro_ce_net_short_change": pro["ce_net_short_chg"],
            "pro_pe_long_change": pro["pe_long_chg"],
            "pro_pe_short_change": pro["pe_short_chg"],
            "pro_pe_net_short_change": pro["pe_net_short_chg"],
            "pro_raw_score": pro_raw_score,

            "dii_fut_net_change": dii["fut_chg"],
            "dii_ce_long_change": dii["ce_long_chg"],
            "dii_ce_short_change": dii["ce_short_chg"],
            "dii_ce_net_short_change": dii["ce_net_short_chg"],
            "dii_pe_long_change": dii["pe_long_chg"],
            "dii_pe_short_change": dii["pe_short_chg"],
            "dii_pe_net_short_change": dii["pe_net_short_chg"],
            "dii_raw_score": dii_raw_score,

            "client_ce_net_buy": client_ce_net_buy,
            "client_pe_net_buy": client_pe_net_buy,

            "fii_fut_net_carried": float(fii_today.get('Future Index Long', 0)) - float(fii_today.get('Future Index Short', 0)),
            "pro_fut_net_carried": float(pro_today.get('Future Index Long', 0)) - float(pro_today.get('Future Index Short', 0)),
            "dii_fut_net_carried": float(dii_today.get('Future Index Long', 0)) - float(dii_today.get('Future Index Short', 0)),

            "weights": {"fii": FII_WEIGHT, "pro": PRO_WEIGHT, "dii": DII_WEIGHT, "client": 0.0},
        }

    except Exception as e:
        print(f"Error parsing FDCP data: {e}")
        return None


# ---------------------------------------------------------------------------
# Everything below (index roll detection, stock breadth scan, multi-day
# conviction, and the run_engine orchestrator) is UNCHANGED from the original
# script - the review did not find weighting/comparison issues in these
# sections, only in participant scoring above.
# ---------------------------------------------------------------------------


def detect_index_rolls(stock_data):
    """
    Detects Resistance & Support Rolls, Magnet Strikes, Expected Expiry Ranges,
    and Operator Squeeze / Trap Alarms for indices (NIFTY, BANKNIFTY, FINNIFTY, MIDCPNIFTY).
    """
    results = {}
    indices = ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"]

    for symbol in indices:
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

        strike_diffs = [near[i+1]["strike"] - near[i]["strike"] for i in range(len(near)-1)]
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

        pain_map = {}
        for target in near:
            tp = target["strike"]
            total_loss = 0
            for s in near:
                st = s["strike"]
                if target["strike"] > st:
                    total_loss += (target["strike"] - st) * s["pe_oi"]
                elif target["strike"] < st:
                    total_loss += (st - target["strike"]) * s["ce_oi"]
            pain_map[tp] = total_loss
        max_pain = min(pain_map, key=pain_map.get) if pain_map else ltp

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

        traps_and_squeezes = []

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
                    "desc": f"Synthetic futures (+{premium:.1f} pts). Operators are loading Calls / Shorting Puts."
                })
            elif premium < -20:
                traps_and_squeezes.append({
                    "type": "SYN_BEAR",
                    "strike": atm_strike["strike"],
                    "badge": "SYNTHETIC DISCOUNT",
                    "desc": f"Synthetic futures ({premium:.1f} pts). Operators are shorting futures via spread Parity."
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
                    "desc": f"Bears forced to cover CE at {st} as LTP ({ltp:,.1f}) crossed above."
                })
            elif ltp < st and adj_pe_doi < trap_threshold and s["pe_oi"] > 5000:
                traps_and_squeezes.append({
                    "type": "PUT_TRAP",
                    "strike": st,
                    "badge": "PUT WRITER TRAP",
                    "desc": f"Bulls trapped at {st} PE as LTP ({ltp:,.1f}) broke below."
                })

        if len(traps_and_squeezes) > 3:
            traps_and_squeezes = traps_and_squeezes[:3]

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


def scan_stock_breadth(stock_data):
    """
    Scans all 215 stocks in option chain data to find top 10 market leaders in:
    1. Fresh Call Writing (Operators Capping Upside → Bearish Stocks)
    2. Fresh Put Writing (Operators Defending Floor → Bullish Stocks)
    3. Call Unwinding (Short Squeeze Risk → Bullish Breakout Stocks)
    4. Put Unwinding (Floor Breakdown Risk → Bearish Stocks)
    """
    call_writing = []
    put_writing = []
    call_unwinding = []
    put_unwinding = []

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

        stock_summary = {
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

        # Dynamic threshold: at least 500 contracts OR 5% of total open interest,
        # whichever is larger. This normalises across low-OI and high-OI stocks.
        ce_threshold = max(500, net_ce_oi * 0.05) if net_ce_oi > 0 else 500
        pe_threshold = max(500, net_pe_oi * 0.05) if net_pe_oi > 0 else 500

        if net_ce_doi > ce_threshold:
            call_writing.append(stock_summary)
        elif net_ce_doi < -ce_threshold:
            call_unwinding.append(stock_summary)

        if net_pe_doi > pe_threshold:
            put_writing.append(stock_summary)
        elif net_pe_doi < -pe_threshold:
            put_unwinding.append(stock_summary)

    call_writing = sorted(call_writing, key=lambda x: x["net_ce_doi"], reverse=True)[:10]
    put_writing = sorted(put_writing, key=lambda x: x["net_pe_doi"], reverse=True)[:10]
    call_unwinding = sorted(call_unwinding, key=lambda x: x["net_ce_doi"])[:10]
    put_unwinding = sorted(put_unwinding, key=lambda x: x["net_pe_doi"])[:10]

    return {
        "call_writing_bearish": call_writing,
        "put_writing_bullish": put_writing,
        "call_unwinding_bullish": call_unwinding,
        "put_unwinding_bearish": put_unwinding,
        "counts": {
            "call_writing": len(call_writing),
            "put_writing": len(put_writing),
            "call_unwinding": len(call_unwinding),
            "put_unwinding": len(put_unwinding),
        },
    }


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
                print(f"Removed old history snapshot: {f_path}")
        except Exception:
            pass


def build_multiday_conviction(history_dir):
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

    conviction = {}
    ref_avg_oi = None  # NIFTY average OI per strike, used as baseline for scaling other indices

    for sym in ["NIFTY", "BANKNIFTY"]:
        multiday_map = {}

        latest_ltp = None
        for f_path in reversed(recent_files):
            try:
                with open(f_path, "r") as f:
                    snap = json.load(f)
                latest_ltp = snap.get("stocks", {}).get(sym, {}).get("ltp")
                if latest_ltp:
                    break
            except Exception:
                continue

        for f_path in recent_files:
            try:
                with open(f_path, "r") as f:
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
                            "today_pe_doi": s.get("pe_change_oi", 0)
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

        # Compute average OI per strike for conviction threshold scaling.
        # NIFTY is the baseline (scale=1.0). Other indices (e.g. BANKNIFTY with ~2x OI)
        # get proportionally scaled thresholds so conviction isn't over-signalled.
        avg_ce_oi = 0
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
        unwind_th = int(2500 * scale)

        for item in sorted_strikes:
            ce_hist = item["ce_oi_history"]
            pe_hist = item["pe_oi_history"]

            if len(ce_hist) >= 2:
                ce_diff = ce_hist[-1] - ce_hist[0]
            else:
                ce_diff = item.get("today_ce_doi", 0)

            item["ce_trend_delta"] = ce_diff
            item["ce_conviction"] = "HARD RESISTANCE" if ce_diff > hard_res_th else "CE BUILDING" if ce_diff > building_th else "CE UNWINDING" if ce_diff < -unwind_th else "STABLE"

            if len(pe_hist) >= 2:
                pe_diff = pe_hist[-1] - pe_hist[0]
            else:
                pe_diff = item.get("today_pe_doi", 0)

            item["pe_trend_delta"] = pe_diff
            item["pe_conviction"] = "SOLID FLOOR" if pe_diff > hard_res_th else "PE BUILDING" if pe_diff > building_th else "PE UNWINDING" if pe_diff < -unwind_th else "STABLE"

        conviction[sym] = {
            "dates": dates,
            "strikes": sorted_strikes
        }

    return conviction


def run_engine():
    """Master runner that processes FDCP + Option Chain + Archives to write money_flow_data.json."""
    print("Running Institutional Verdict Engine...")

    if not os.path.exists(NSE_DATA_FILE):
        print(f"Error: {NSE_DATA_FILE} not found. Run OC.py first.")
        return

    with open(NSE_DATA_FILE, "r") as f:
        oc_raw = json.load(f)

    timestamp = oc_raw.get("timestamp", datetime.now(timezone.utc).isoformat())
    stocks = oc_raw.get("stocks", {})

    participant_summary = load_participant_data()
    index_rolls = detect_index_rolls(stocks)
    stock_breadth = scan_stock_breadth(stocks)
    conviction_trends = build_multiday_conviction(HISTORY_DIR)

    score_breakdown = {}
    if participant_summary:
        score_breakdown = {
            "fii_raw_score": participant_summary.get("fii_raw_score", 0),
            "pro_raw_score": participant_summary.get("pro_raw_score", 0),
            "dii_raw_score": participant_summary.get("dii_raw_score", 0),
            "fii_weight": FII_WEIGHT,
            "pro_weight": PRO_WEIGHT,
            "dii_weight": DII_WEIGHT,
            "weighted_clipped_before_trap": participant_summary.get("weighted_clipped_before_trap", 0),
            "trap_adjustment": participant_summary.get("trap_adjustment", 0),
        }

    verdict_payload = {
        "timestamp": timestamp,
        "executive_summary": {
            "bias_label": participant_summary["bias_label"] if participant_summary else "NEUTRAL",
            "smart_money_score": participant_summary["smart_money_score"] if participant_summary else 0,
            "action_desc": participant_summary["action_desc"] if participant_summary else "No participant data available.",
            "score_breakdown": score_breakdown,
        },
        "participant_summary": participant_summary,
        "index_rolls": index_rolls,
        "stock_breadth": stock_breadth,
        "conviction_trends": conviction_trends,
        "stock_count": len(stocks),
    }

    cleaned = clean_val(verdict_payload)

    with open(OUTPUT_FILE, "w") as f:
        json.dump(cleaned, f, indent=2)

    print(f"[OK] Success! Institutional Verdict saved to {OUTPUT_FILE}")
    print(f"   Bias: {verdict_payload['executive_summary']['bias_label']}")
    print(f"   Index Rolls: {list(index_rolls.keys())}")
    print(f"   Stock Breadth: Call Write={len(stock_breadth['call_writing_bearish'])}, Put Write={len(stock_breadth['put_writing_bullish'])}")


if __name__ == "__main__":
    import sys

    dry_run = "--dry-run" in sys.argv

    if dry_run:
        print("=" * 60)
        print("  DRY RUN MODE — Scoring Diagnostics Only")
        print("=" * 60)
        print()
        # Run only the participant data scoring
        participant_data = load_participant_data()
        if participant_data:
            print(f"Date: {participant_data['date']}  ->  {participant_data['prev_date']}")
            print()
            print(f"Smart Money Score: {participant_data['smart_money_score']}")
            print(f"Bias Label: {participant_data['bias_label']}")
            print(f"Retail Trap Alarm: {participant_data.get('retail_trap_alarm', 'None')}")
            print()
            print("-- Raw Scores (proportional, per-participant thresholds) --")
            print(f"  FII  raw_score = {participant_data.get('fii_raw_score', 'N/A')}  (weight={FII_WEIGHT}, fut_th={FII_FUT_THRESHOLD}, opt_th={FII_OPT_THRESHOLD})")
            print(f"  Pro  raw_score = {participant_data.get('pro_raw_score', 'N/A')}  (weight={PRO_WEIGHT}, fut_th={PRO_FUT_THRESHOLD}, opt_th={PRO_OPT_THRESHOLD})")
            print(f"  DII  raw_score = {participant_data.get('dii_raw_score', 'N/A')}  (weight={DII_WEIGHT}, fut_th={DII_FUT_THRESHOLD}, opt_th={DII_OPT_THRESHOLD})")
            weighted = (
                participant_data.get("fii_raw_score", 0) * FII_WEIGHT
                + participant_data.get("pro_raw_score", 0) * PRO_WEIGHT
                + participant_data.get("dii_raw_score", 0) * DII_WEIGHT
            )
            weighted_clipped = max(-SCORE_CLIP, min(SCORE_CLIP, weighted))
            trap_adj = participant_data.get("trap_adjustment", 0)
            clipped_before_trap = participant_data.get("weighted_clipped_before_trap", weighted_clipped)
            print(f"\n  Weighted composite (before clip): {weighted:.1f}")
            print(f"  After clip [{SCORE_CLIP}]: {weighted_clipped}")
            print(f"  Clipped before trap adj: {clipped_before_trap}")
            print(f"  Trap adjustment applied: {trap_adj}")
            print(f"  Final score: {participant_data['smart_money_score']}")
            print()
            print("-- Participant Data --")
            for key in ["fii_fut_net_change", "fii_ce_net_short_change", "fii_pe_net_short_change",
                        "pro_fut_net_change", "pro_ce_net_short_change", "pro_pe_net_short_change",
                        "client_ce_net_buy", "client_pe_net_buy"]:
                print(f"  {key}: {participant_data.get(key, 'N/A')}")
        else:
            print("ERROR: No participant data available. Check FDCP_Data.csv.")
        print()
        print("Dry run complete. No output file written.")
    else:
        run_engine()