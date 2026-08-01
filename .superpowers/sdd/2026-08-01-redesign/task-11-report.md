# Task 11 Report — engine.py nested schema

**Status:** DONE

## What was implemented

`nse_toolkit/engine.py` (in `run_engine`):
1. Added module-level `_nested_summary(ps: dict) -> dict` helper (per brief) that maps flat `participant_summary` → nested `verdict` / `participants` / `retail` / `weights`.
2. Replaced the `verdict_payload` block (was ~lines 967–981):
   - `participant_summary` kept flat and untouched (telegram.py compat).
   - New top-level keys: `verdict`, `participants` (fii/pro/dii/client), `retail`, `weights`.
   - Renamed: `index_rolls`→`rolls`, `stock_breadth`→`breadth`, `conviction_trends`→`conviction`, `flow_divergence`→`divergence`. Old keys removed from payload.
   - Inner structures unchanged (snake_case preserved).
   - Null-safe path when `participant_summary` is falsy (empty nested dicts, score 0, NEUTRAL).

## Deviation from brief

Brief's `client.futures` block omitted `stockLong`/`stockShort`/`netCarried`, but the cross-task contract (from `views/verdict.js` review) requires **all 7 futures keys on every participant**. Added them for client:
- `stockLong` ← `client_stk_fut_long_change`, `stockShort` ← `client_stk_fut_short_change` (both exist in flat data).
- `netCarried` ← `ps.get("client_fut_net_carried", 0)` — **no such flat key exists**; defaults to 0. Harmless: verdict.js never reads `client.futures.*` (Retail row uses `client.options.ce.netBuy`). Marked with `ponytail:` comment; if engine ever computes client carried, wire it here.

## Verification

1. `python main.py engine --dry-run` — diagnostics only, no write. PASS.
2. `python main.py engine` — wrote `docs/money_flow_data.json`. Bias MODERATE BEARISH.
3. JSON shape check (inline python):
   - All top keys present: `timestamp, executive_summary, participant_summary, verdict, participants, retail, weights, rolls, breadth, conviction, divergence, stock_count`.
   - `participant_summary` still present + flat (telegram compat).
   - Contract spot-checks all pass:
     - `participants.fii.futures.net == participant_summary.fii_fut_net_change`
     - `fii.options.ce.netShort == fii_ce_net_short_change`, `pro.pe.netShort == pro_pe_net_short_change`
     - `client.options.ce.netBuy == client_ce_net_buy`, `client.futures.net == client_fut_net_change`
     - `verdict.score/bias/actionDesc == smart_money_score/bias_label/action_desc`
     - `retail.trapAlarm/adjustment == retail_trap_alarm/trap_adjustment`
     - `weights` equal.
     - All four participants have all 7 futures keys.
   - Inner structures intact: rolls have `resistance_roll_type`, `magnet_strike`, `expiry_range`; breadth has 4 columns + `counts`; conviction has strikes with `ce_conviction`/`pe_conviction`/`ce_flow_attr`; divergence items have `symbol/strike/type/desc/signal`.
   - Old keys `index_rolls/stock_breadth/conviction_trends/flow_divergence` gone from payload.
4. Telegram compat: `python -c "from nse_toolkit.telegram import build_takeaways_message; print(build_takeaways_message())"` → `True` + Bearish message (reads flat participant_summary). PASS.
5. Headless Chrome (playwright, `verify_t11.py`, screenshot `t11_verdict.png`):
   - **Nested-path precedence proven**: mutated only nested keys (banner: score 12345, bias "NESTED BIAS MARKER", actionDesc marker; all 9 stance rows got distinct nested values), nulled the flat keys verdict.js stance rows read, then confirmed rendered DOM shows the nested values:
     - Banner badge/gauge/desc show nested markers.
     - 9 stance rows all render nested values (FII call 9,876, FII put 5,555, FII fut 1,11,111, Pro call 6,666, Pro put 7,777, Retail 8,888, DII call 9,999, DII put 10,101, DII fut 1,21,212).
     - Rolls (4 cards), conviction tabs (2) + 15 rows, divergence (8 items), breadth (4 cols) all render.
   - No console errors, no unexpected 404s (only the known charts.js Task-10 404).
   - Data file restored to engine output after test.
   - VERDICT: **PASS — NESTED PATH WINS**.

## Files changed

- `nse_toolkit/engine.py` — nested schema + `_nested_summary`.
- `docs/money_flow_data.json` — regenerated (tracked, expected per brief).
- `.superpowers/sdd/2026-08-01-redesign/verify_t11.py` — new headless-Chrome verification harness (kept alongside other task verify scripts).

## Self-review

- `participant_summary` untouched — telegram.py still reads it (verified).
- Schema matches verdict.js exactly (all contract keys verified against real data + DOM).
- `verdict.scoreBreakdown` maps from flat `weights` (verdict.js doesn't read it, but harmless and per brief).
- Nullable retail keys (`trapAlarm`, `confirmationMessage`) left as-is (None when absent) — JSON dumps null, frontend handles undefined/null fine.

## Concerns

- `participants.client.futures.netCarried` defaults to 0 (no source flat key). Cosmetic only.
- Stance panel still prefers flat keys when present (`ps.x ?? nested.x` in verdict.js). Nested values are identical to flat by construction, so no behavioral difference; nested path is exercised only when flat is absent. Flagged to reviewer — verdict.js is committed/correct per its review, schema matches.
