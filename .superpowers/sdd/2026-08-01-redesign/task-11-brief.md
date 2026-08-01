### Task 11: engine.py — nested schema alongside flat participant_summary

**Files:**
- Modify: `nse_toolkit/engine.py` (in `run_engine`, the `verdict_payload` construction ~line 967)
- Test: verify JSON shape after run

**Interfaces:**
- Consumes: existing `participant_summary` dict (flat keys unchanged).
- Produces: `money_flow_data.json` top-level keys: `timestamp`, `executive_summary` (unchanged), `participant_summary` (unchanged — telegram compat), **new** `verdict`, `participants`, `retail`; renames `index_rolls`→`rolls`, `stock_breadth`→`breadth`, `conviction_trends`→`conviction`, `flow_divergence`→`divergence`. Inner structures unchanged (snake_case preserved).

- [ ] **Step 1: Add `_nested_summary` helper (top of run_engine or module level)**

```python
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
```

- [ ] **Step 2: Modify verdict_payload in run_engine**

Replace the `verdict_payload = {...}` block (currently lines ~967–981) with:

```python
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
```

- [ ] **Step 3: Verify engine output**

Run `python main.py engine --dry-run` (no write) then `python main.py engine` (writes). Check `docs/money_flow_data.json`:
- `participant_summary` still present + flat (telegram compat).
- New `verdict`, `participants` (fii/pro/dii/client), `retail`, `rolls`, `breadth`, `conviction`, `divergence` keys present.
- Spot-check `participants.fii.futures.net == participant_summary.fii_fut_net_change`.
- `python -c "from nse_toolkit.telegram import build_takeaways_message; print(build_takeaways_message()[:80])"` still works (reads participant_summary).

- [ ] **Step 4: Commit**

```bash
git add nse_toolkit/engine.py docs/money_flow_data.json
git commit -m "feat(engine): emit nested schema, keep flat participant_summary for telegram"
```

---

