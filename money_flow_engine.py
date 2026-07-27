"""
Money Flow & Institutional Verdict Engine
------------------------------------------
Cross-correlates Gross Participant OI (FDCP_Data.csv) with Strike-Level Option Chains (nse_data.json)
and multi-day snapshot archives (docs/oc_history/) to deliver institutional verdicts.

Verdict Categories:
1. Executive Market Verdict (Bullish / Bearish / Sideways + Confidence Score)
2. FII Options Stance (Call/Put Short additions/reductions from FDCP)
3. Index Roll Intelligence (Resistance & Support Roll direction & magnitude)
4. Stock F&O Breadth (Top Call/Put writing & unwinding stocks across all 215 symbols)
5. Multi-Day Strike Conviction Heatmap (Indices & major stocks)
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


def load_participant_data():
    """Load latest FDCP data and derive FII & Pro daily positioning shifts."""
    if not os.path.exists(FDCP_FILE):
        return None

    try:
        df = pd.read_csv(FDCP_FILE)
        df.columns = df.columns.str.strip()
        
        # Ensure rows are ordered by Date
        dates = df['Date'].unique()
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
        client_today = get_row('Client', latest_date)
        client_prev = get_row('Client', prev_date)

        def calc_chg(row_t, row_p, col):
            return float(row_t.get(col, 0)) - float(row_p.get(col, 0)) if row_t and row_p else 0.0

        # FII Index Shifts
        fii_fut_chg = calc_chg(fii_today, fii_prev, 'Future Index Long') - calc_chg(fii_today, fii_prev, 'Future Index Short')
        fii_ce_long_chg = calc_chg(fii_today, fii_prev, 'Option Index Call Long')
        fii_ce_short_chg = calc_chg(fii_today, fii_prev, 'Option Index Call Short')
        fii_pe_long_chg = calc_chg(fii_today, fii_prev, 'Option Index Put Long')
        fii_pe_short_chg = calc_chg(fii_today, fii_prev, 'Option Index Put Short')

        # Pro Index Shifts
        pro_fut_chg = calc_chg(pro_today, pro_prev, 'Future Index Long') - calc_chg(pro_today, pro_prev, 'Future Index Short')
        pro_ce_short_chg = calc_chg(pro_today, pro_prev, 'Option Index Call Short')
        pro_pe_short_chg = calc_chg(pro_today, pro_prev, 'Option Index Put Short')

        # Client (Retail) Index Shifts
        client_ce_long_chg = calc_chg(client_today, client_prev, 'Option Index Call Long')
        client_ce_short_chg = calc_chg(client_today, client_prev, 'Option Index Call Short')
        client_ce_net_buy = client_ce_long_chg - client_ce_short_chg

        # FII Option Writing Verdict
        # CE Short Add → FII Capping Upside (Bearish)
        # CE Short Cut → FII Unwinding Resistance (Bullish)
        # PE Short Add → FII Defending Floor (Bullish)
        # PE Short Cut → FII Abandoning Floor (Bearish)
        fii_ce_net_short_chg = fii_ce_short_chg - fii_ce_long_chg
        fii_pe_net_short_chg = fii_pe_short_chg - fii_pe_long_chg

        # Institutional Score (-100 to +100)
        # Positive = FII/Pro Net Buying / Put Writing; Negative = Selling / Call Writing
        score = 0
        if fii_fut_chg > 5000: score += 25
        elif fii_fut_chg < -5000: score -= 25

        if fii_ce_net_short_chg < -10000: score += 25  # Covering calls = bullish
        elif fii_ce_net_short_chg > 10000: score -= 25  # Writing calls = bearish

        if fii_pe_net_short_chg > 10000: score += 25  # Writing puts = bullish floor
        elif fii_pe_net_short_chg < -10000: score -= 25  # Unwinding puts = bearish floor drop

        if pro_pe_short_chg > pro_ce_short_chg: score += 15
        elif pro_ce_short_chg > pro_pe_short_chg: score -= 15

        # Feature 4: Retail Trap / Contrarian Sentiment Filter
        retail_trap_alarm = None
        if client_ce_net_buy > 25000 and fii_ce_net_short_chg > 10000:
            score -= 15
            retail_trap_alarm = "⚠️ RETAIL CALL TRAP: Retail buying calls while FIIs aggressively write calls."
        elif client_ce_net_buy < -25000 and fii_pe_net_short_chg > 10000:
            score += 15
            retail_trap_alarm = "🚀 RETAIL PUT TRAP: Retail buying puts while FIIs aggressively write puts."

        if score >= 40:
            bias_label = "HIGH CONFIDENCE BULLISH"
            action_desc = "FII & Pro desks are aggressively covering Call shorts and building Put floors."
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

        # Pro Options Verdict
        pro_ce_long_chg = calc_chg(pro_today, pro_prev, 'Option Index Call Long')
        pro_pe_long_chg = calc_chg(pro_today, pro_prev, 'Option Index Put Long')
        pro_ce_net_short_chg = pro_ce_short_chg - pro_ce_long_chg
        pro_pe_net_short_chg = pro_pe_short_chg - pro_pe_long_chg

        # Client (Retail) Options Verdict
        client_pe_long_chg = calc_chg(client_today, client_prev, 'Option Index Put Long')
        client_pe_short_chg = calc_chg(client_today, client_prev, 'Option Index Put Short')
        client_pe_net_buy = client_pe_long_chg - client_pe_short_chg

        return {
            "date": latest_date,
            "prev_date": prev_date,
            "smart_money_score": score,
            "bias_label": bias_label,
            "action_desc": action_desc,
            "retail_trap_alarm": retail_trap_alarm,
            "fii_fut_net_change": fii_fut_chg,
            "fii_ce_short_change": fii_ce_short_chg,
            "fii_ce_long_change": fii_ce_long_chg,
            "fii_ce_net_short_change": fii_ce_net_short_chg,
            "fii_pe_short_change": fii_pe_short_chg,
            "fii_pe_long_change": fii_pe_long_chg,
            "fii_pe_net_short_change": fii_pe_net_short_chg,
            "pro_fut_net_change": pro_fut_chg,
            "pro_ce_short_change": pro_ce_short_chg,
            "pro_pe_short_change": pro_pe_short_chg,
            "pro_ce_net_short_change": pro_ce_net_short_chg,
            "pro_pe_net_short_change": pro_pe_net_short_chg,
            "client_ce_net_buy": client_ce_net_buy,
            "client_pe_net_buy": client_pe_net_buy,
            "fii_fut_net_carried": float(fii_today.get('Future Index Long', 0)) - float(fii_today.get('Future Index Short', 0)),
            "pro_fut_net_carried": float(pro_today.get('Future Index Long', 0)) - float(pro_today.get('Future Index Short', 0)),
        }

    except Exception as e:
        print(f"Error parsing FDCP data: {e}")
        return None


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

        # Sort strikes
        strikes = sorted(strikes, key=lambda x: x["strike"])

        # Filter near-the-money range (+/- 6% of LTP)
        near = [s for s in strikes if abs(s["strike"] - ltp) / ltp <= 0.06]
        if not near:
            near = strikes

        # Step size between strikes (e.g. 50 for NIFTY, 100 for BANKNIFTY)
        strike_diffs = [near[i+1]["strike"] - near[i]["strike"] for i in range(len(near)-1)]
        step_size = float(np.median(strike_diffs)) if strike_diffs else 50.0
        if step_size <= 0:
            step_size = 50.0

        # Find strike with max total CE OI (Current Resistance)
        res_wall = max(near, key=lambda x: x["ce_oi"])["strike"]
        # Find strike with max fresh CE ΔOI (Fresh Call Writing / New Resistance)
        fresh_res = max(near, key=lambda x: x["ce_change_oi"])["strike"]
        # Find strike with max CE ΔOI unwinding (Call Unwinding / Dismantled Resistance)
        unwind_res_obj = min(near, key=lambda x: x["ce_change_oi"])
        unwind_res = unwind_res_obj["strike"] if unwind_res_obj["ce_change_oi"] < -500 else None

        # Find strike with max total PE OI (Current Support)
        sup_wall = max(near, key=lambda x: x["pe_oi"])["strike"]
        # Find strike with max fresh PE ΔOI (Fresh Put Writing / New Support Floor)
        fresh_sup = max(near, key=lambda x: x["pe_change_oi"])["strike"]
        # Find strike with max PE ΔOI unwinding (Put Unwinding / Broken Floor)
        unwind_sup_obj = min(near, key=lambda x: x["pe_change_oi"])
        unwind_sup = unwind_sup_obj["strike"] if unwind_sup_obj["pe_change_oi"] < -500 else None

        # ── Feature 1: Magnet Strike & Expected Expiry Range ─────────
        # Compute Max Pain
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

        # Magnet Strike = Weighted blend of Max Pain, Max CE Wall, Max PE Wall
        magnet_strike = round((max_pain * 0.5 + res_wall * 0.25 + sup_wall * 0.25) / step_size) * step_size
        expiry_min = round((min(sup_wall, max_pain) - step_size) / step_size) * step_size
        expiry_max = round((max(res_wall, max_pain) + step_size) / step_size) * step_size
        expiry_range_str = f"{int(expiry_min):,} – {int(expiry_max):,}"

        # ── DTE Expiry Decay Calibration ──────────────
        from datetime import datetime
        try:
            exp_date = datetime.strptime(expiry, "%d-%b-%Y") if expiry else datetime.now()
            dte = max(0, (exp_date - datetime.now()).days)
        except Exception:
            dte = 0
        
        # Increase weight of OI buildup if it is far from expiry (pos conviction), decrease if 0 DTE (theta hedging)
        dte_weight = 1.0 + (dte * 0.15)

        # ── Feature 2: Operator Squeeze & Trap Detector (Dynamic IV Scaled) ─────────────
        traps_and_squeezes = []
        
        # Dynamic Scoring Thresholds Based on IV Skew
        # When IV is high, typical position size drops, lower the trap barrier
        avg_iv = float(np.mean([max(s.get("ce_iv", 15), 1) + max(s.get("pe_iv", 15), 1) for s in near])) / 2.0 if near else 15.0
        iv_multiplier = max(0.5, min(2.0, avg_iv / 15.0))
        trap_threshold = -5000 / iv_multiplier  # If IV=30, threshold drops to -2500

        # Synthetic Futures Parity Divergence
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
                    "badge": "🟢 SYNTHETIC PREMIUM",
                    "desc": f"Synthetic futures (+{premium:.1f} pts). Operators are loading Calls / Shorting Puts."
                })
            elif premium < -20:
                traps_and_squeezes.append({
                    "type": "SYN_BEAR",
                    "strike": atm_strike["strike"],
                    "badge": "🔴 SYNTHETIC DISCOUNT",
                    "desc": f"Synthetic futures ({premium:.1f} pts). Operators are shorting futures via spread Parity."
                })

        for s in near:
            st = s["strike"]
            # Only check active strikes near current market price (+/- 1.5% of LTP)
            if abs(st - ltp) / ltp > 0.015:
                continue

            # Apply Expiry Decay to OI changes
            adj_ce_doi = s["ce_change_oi"] * dte_weight
            adj_pe_doi = s["pe_change_oi"] * dte_weight

            # Call Squeeze: Price > Strike AND CE is unwinding heavily near ATM
            if ltp > st and adj_ce_doi < trap_threshold and s["ce_oi"] > 5000:
                traps_and_squeezes.append({
                    "type": "CALL_SQUEEZE",
                    "strike": st,
                    "badge": "🚀 CALL WRITER SQUEEZE",
                    "desc": f"Bears forced to cover CE at {st} as LTP ({ltp:,.1f}) crossed above."
                })
            # Put Trap: Price < Strike AND PE is unwinding heavily near ATM
            elif ltp < st and adj_pe_doi < trap_threshold and s["pe_oi"] > 5000:
                traps_and_squeezes.append({
                    "type": "PUT_TRAP",
                    "strike": st,
                    "badge": "⚠️ PUT WRITER TRAP",
                    "desc": f"Bulls trapped at {st} PE as LTP ({ltp:,.1f}) broke below."
                })

        # Keep max 3 highest-priority alerts to avoid UI clutter
        if len(traps_and_squeezes) > 3:
            traps_and_squeezes = traps_and_squeezes[:3]

        # ── Resistance & Support Roll Verdicts ───────────────────────
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

        # PCRs
        tot_ce_oi = sum(s["ce_oi"] for s in near)
        tot_pe_oi = sum(s["pe_oi"] for s in near)
        tot_ce_doi = sum(s["ce_change_oi"] for s in near)
        tot_pe_doi = sum(s["pe_change_oi"] for s in near)

        pcr_oi = (tot_pe_oi / tot_ce_oi) if tot_ce_oi > 0 else 1.0
        pcr_doi = (tot_pe_doi / tot_ce_doi) if tot_ce_doi > 0 else 1.0

        # Feature 4: Divergence Signal
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

        # Aggregates across all strikes for this stock
        net_ce_doi = sum(s["ce_change_oi"] for s in strikes)
        net_pe_doi = sum(s["pe_change_oi"] for s in strikes)
        net_ce_oi = sum(s["ce_oi"] for s in strikes)
        net_pe_oi = sum(s["pe_oi"] for s in strikes)

        # Single largest strike ΔOI action for detailed callout
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

        if net_ce_doi > 500:
            call_writing.append(stock_summary)
        elif net_ce_doi < -500:
            call_unwinding.append(stock_summary)

        if net_pe_doi > 500:
            put_writing.append(stock_summary)
        elif net_pe_doi < -500:
            put_unwinding.append(stock_summary)

    # Sort each list by ΔOI magnitude
    call_writing = sorted(call_writing, key=lambda x: x["net_ce_doi"], reverse=True)[:10]
    put_writing = sorted(put_writing, key=lambda x: x["net_pe_doi"], reverse=True)[:10]
    call_unwinding = sorted(call_unwinding, key=lambda x: x["net_ce_doi"])[:10]  # Most negative
    put_unwinding = sorted(put_unwinding, key=lambda x: x["net_pe_doi"])[:10]  # Most negative

    return {
        "call_writing_bearish": call_writing,
        "put_writing_bullish": put_writing,
        "call_unwinding_bullish": call_unwinding,
        "put_unwinding_bearish": put_unwinding,
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
    # First clean up files older than 30 days
    cleanup_old_history(history_dir, max_days=30)

    files = sorted(glob.glob(os.path.join(history_dir, "*.json")))
    if not files:
        return {}

    # Take up to last 5 archived days
    recent_files = files[-5:]
    dates = [os.path.basename(f).replace(".json", "") for f in recent_files]

    conviction = {}

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
                    if abs(st - ltp) / ltp > 0.04:  # +/- 4% range
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

        # Filter 15 strikes centered around latest_ltp
        all_strikes = list(multiday_map.values())
        if latest_ltp and all_strikes:
            all_strikes = sorted(all_strikes, key=lambda x: abs(x["strike"] - latest_ltp))[:15]
            sorted_strikes = sorted(all_strikes, key=lambda x: x["strike"])
        else:
            sorted_strikes = sorted(all_strikes, key=lambda x: x["strike"])[:15]

        # Compute trend conviction label per strike
        for item in sorted_strikes:
            ce_hist = item["ce_oi_history"]
            pe_hist = item["pe_oi_history"]

            # CE Trend
            if len(ce_hist) >= 2:
                ce_diff = ce_hist[-1] - ce_hist[0]
            else:
                ce_diff = item.get("today_ce_doi", 0)

            item["ce_trend_delta"] = ce_diff
            item["ce_conviction"] = "HARD RESISTANCE" if ce_diff > 25000 else "CE BUILDING" if ce_diff > 2500 else "CE UNWINDING" if ce_diff < -2500 else "STABLE"

            # PE Trend
            if len(pe_hist) >= 2:
                pe_diff = pe_hist[-1] - pe_hist[0]
            else:
                pe_diff = item.get("today_pe_doi", 0)

            item["pe_trend_delta"] = pe_diff
            item["pe_conviction"] = "SOLID FLOOR" if pe_diff > 25000 else "PE BUILDING" if pe_diff > 2500 else "PE UNWINDING" if pe_diff < -2500 else "STABLE"

        conviction[sym] = {
            "dates": dates,
            "strikes": sorted_strikes
        }

    return conviction


def run_engine():
    """Master runner that processes FDCP + Option Chain + Archives to write money_flow_data.json."""
    print("Running Institutional Verdict Engine...")

    # Load option chain snapshot
    if not os.path.exists(NSE_DATA_FILE):
        print(f"Error: {NSE_DATA_FILE} not found. Run OC.py first.")
        return

    with open(NSE_DATA_FILE, "r") as f:
        oc_raw = json.load(f)

    timestamp = oc_raw.get("timestamp", datetime.now(timezone.utc).isoformat())
    stocks = oc_raw.get("stocks", {})

    # 1. Load FDCP Participant Positioning
    participant_summary = load_participant_data()

    # 2. Detect Index Resistance & Support Rolls
    index_rolls = detect_index_rolls(stocks)

    # 3. Scan Stock Breadth Across All 215 Symbols
    stock_breadth = scan_stock_breadth(stocks)

    # 4. Compute Multi-Day Conviction from Archived History
    conviction_trends = build_multiday_conviction(HISTORY_DIR)

    # Combine into Master Verdict Payload
    verdict_payload = {
        "timestamp": timestamp,
        "executive_summary": {
            "bias_label": participant_summary["bias_label"] if participant_summary else "NEUTRAL",
            "smart_money_score": participant_summary["smart_money_score"] if participant_summary else 0,
            "action_desc": participant_summary["action_desc"] if participant_summary else "No participant data available.",
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

    print(f"✅ Success! Institutional Verdict saved to {OUTPUT_FILE}")
    print(f"   Bias: {verdict_payload['executive_summary']['bias_label']}")
    print(f"   Index Rolls: {list(index_rolls.keys())}")
    print(f"   Stock Breadth: Call Write={len(stock_breadth['call_writing_bearish'])}, Put Write={len(stock_breadth['put_writing_bullish'])}")


if __name__ == "__main__":
    run_engine()
