"""
NFOD Unified CLI — run any or all phases of the daily data pipeline.

Usage:
    python main.py all                    # Run everything sequentially
    python main.py fdcp                   # Fetch FDCP participant OI data only
    python main.py oc                     # Fetch option chain data only
    python main.py ohlc                   # Fetch NIFTY OHLC data only
    python main.py cpr                    # Compute CPR for major NSE indices
    python main.py engine                 # Run verdict engine only
    python main.py engine --dry-run       # Run engine in dry-run (diagnostics) mode
    python main.py prerender              # Prerender static HTML into index.html
    python main.py telegram               # Send Gross OI page to Telegram
"""

import argparse
from nse_toolkit.fetcher import fetch_fdcp, fetch_option_chain, fetch_ohlc, update_embedded_csv
from nse_toolkit.engine import run_engine, load_participant_data, compute_iv_modifier
from nse_toolkit.telegram import send_gross_oi_telegram
from nse_toolkit.prerender import prerender_index
from nse_toolkit.cpr import get_today_cpr, get_prior_day_cpr
from nse_toolkit.config import SCORE_CLIP, FII_WEIGHT, PRO_WEIGHT, DII_WEIGHT, NSE_DATA_FILE
from nse_toolkit.config import FII_FUT_THRESHOLD, FII_OPT_THRESHOLD, PRO_FUT_THRESHOLD, PRO_OPT_THRESHOLD, DII_FUT_THRESHOLD, DII_OPT_THRESHOLD
import json
import os


def cmd_fdcp():
    fetch_fdcp()
    update_embedded_csv()


def cmd_oc():
    fetch_option_chain()


def cmd_ohlc():
    fetch_ohlc()


def cmd_cpr():
    """Compute CPR for NIFTY, NIFTYBANK."""
    for sym in ["NIFTY", "BANK"]:
        try:
            prior = get_prior_day_cpr(sym)
            today = get_today_cpr(sym)
            print(f"\n{sym}:")
            print(f"  Prior-day CPR: P={prior['pivot']:.2f} F={prior['floor']:.2f} C={prior['ceiling']:.2f} range={prior['range']:.2f}")
            print(f"  Today CPR:    P={today['pivot']:.2f} F={today['floor']:.2f} C={today['ceiling']:.2f} range={today['range']:.2f}")
        except Exception as e:
            print(f"\n{sym}: CPR computation failed — {e}")


def cmd_engine(dry_run: bool = False):
    if dry_run:
        print("=" * 60)
        print("  DRY RUN MODE — Scoring Diagnostics Only")
        print("=" * 60)
        print()
        iv_mod = 0
        if os.path.exists(NSE_DATA_FILE):
            with open(NSE_DATA_FILE) as f:
                oc_raw = json.load(f)
            iv_mod = compute_iv_modifier(oc_raw.get("stocks", {}))
            print(f"Loaded NSE data. IV modifier: {iv_mod:+.0f}")
        else:
            print("NSE data file not found — IV modifier set to 0.")

        participant_data = load_participant_data(iv_modifier=iv_mod)
        if participant_data:
            print(f"Date: {participant_data['date']}  ->  {participant_data['prev_date']}")
            print()
            print(f"Smart Money Score: {participant_data['smart_money_score']}")
            print(f"Bias Label: {participant_data['bias_label']}")
            trap_msg = participant_data.get("retail_trap_alarm") or participant_data.get("retail_confirmation_message") or "None"
            print(f"Retail Verdict: {trap_msg}")
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
            conf_score = participant_data.get("retail_confirmation_score", 0)
            fii_dii_mod = participant_data.get("fii_dii_modifier", 0)
            iv_mod = participant_data.get("iv_modifier_applied", 0)
            clipped_before = participant_data.get("weighted_clipped_before_adjustments", weighted_clipped)
            print(f"\n  Weighted composite (before clip): {weighted:.1f}")
            print(f"  After clip [{SCORE_CLIP}]: {weighted_clipped}")
            print(f"  Clipped before adjustments: {clipped_before}")
            print(f"  FII-DII alignment modifier: {fii_dii_mod:+.0f}")
            print(f"  Trap adjustment: {trap_adj:+.0f}")
            print(f"  Retail confirmation: {conf_score:+.0f}")
            print(f"  IV modifier: {iv_mod:+.0f}")
            print(f"  Final score: {participant_data['smart_money_score']}")
            print()
            print("-- Participant Data --")
            for key in [
                "fii_fut_net_change", "fii_ce_net_short_change", "fii_pe_net_short_change",
                "pro_fut_net_change", "pro_ce_net_short_change", "pro_pe_net_short_change",
                "client_ce_net_buy", "client_pe_net_buy",
            ]:
                print(f"  {key}: {participant_data.get(key, 'N/A')}")
        else:
            print("ERROR: No participant data available. Check FDCP_Data.csv.")
        print()
        print("Dry run complete. No output file written.")
    else:
        run_engine()


def cmd_prerender():
    prerender_index()


def cmd_telegram():
    send_gross_oi_telegram()


def cmd_all():
    print("\n=== Phase 1: FDCP Fetch ===")
    cmd_fdcp()
    print("\n=== Phase 2: Option Chain Fetch ===")
    cmd_oc()
    print("\n=== Phase 3: OHLC Fetch ===")
    cmd_ohlc()
    print("\n=== Phase 4: Verdict Engine ===")
    cmd_engine()
    print("\n=== Phase 5: Prerender Static HTML ===")
    cmd_prerender()
    print("\n=== Phase 6: Telegram Gross OI ===")
    cmd_telegram()
    print("\n=== Phase 7: CPR Calculation ===")
    cmd_cpr()
    print("\n=== All phases complete! ===")


def main():
    parser = argparse.ArgumentParser(
        description="NFOD — NSE F&O Data Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="all",
        choices=["all", "fdcp", "oc", "ohlc", "engine", "prerender", "telegram", "cpr"],
        help="Pipeline phase to run (default: all)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="For 'engine': run scoring diagnostics without writing output",
    )

    args = parser.parse_args()

    if args.command == "all":
        cmd_all()
    elif args.command == "fdcp":
        cmd_fdcp()
    elif args.command == "oc":
        cmd_oc()
    elif args.command == "ohlc":
        cmd_ohlc()
    elif args.command == "engine":
        cmd_engine(dry_run=args.dry_run)
    elif args.command == "prerender":
        cmd_prerender()
    elif args.command == "telegram":
        cmd_telegram()
    elif args.command == "cpr":
        cmd_cpr()


if __name__ == "__main__":
    main()
