# Task 2 Report: data.js + fetcher.py contract swap

## Status: DONE

## What was implemented

1. **Created `data.js`** at repo root. First two statements on ONE line, byte-for-byte CSV lifted from `app.js` (26148 chars, `\r\n` literal escapes preserved, header trailing spaces intact):
   ```js
   var _EMBEDDED_CSV="<csv>";let rawCSVData=[];
   ```
   Then the exact parse + fetch logic from the brief: `parseCSV(csv)` (strips trailing header spaces + surrounding quotes via `.trim().replace(/^"|"$/g,"")`), `NFOD.data` IIFE exposing `{ availableDates, getParticipantMap, loadMoneyFlow, loadOHLC, parseCSV, rawCSVData }`, using `NFOD.utils.sortDatesChronological` / `NFOD.utils.cacheBust` from Task 1's `lib/utils.js`.

2. **Retargeted `nse_toolkit/fetcher.py:update_embedded_csv()`** from `app.js` to `data.js`. The `prefix`/`suffix` boundary strings are unchanged. Additionally updated three hardcoded log messages that still said "app.js" to use the `appjs_path` variable, so the "not found" and success logs now report the correct filename (this is beyond the one-line brief change but required for the brief's expected log `[EMBED] Updated data.js embedded CSV (N dates).` to actually print). No other logic touched.

## Verification

Commands and output:

1. **Updater run** (from repo root):
   ```
   python _verify_task2.py   # runs update_embedded_csv()
   [EMBED] Updated data.js embedded CSV (43 dates).
   ```
   All contract asserts passed:
   - `single-line first statements: OK`
   - `seam contiguous: '";let rawCSVData'` — no newline between closing quote and `let`
   - `CSV round-trip OK: csv_len=26148 total_rows=216 dates=43 last_date=31-07-2026`
   - `headers[0]: Client Type | headers[3]: 'Future Stock Long' | headers[-1]: Date` (trailing spaces in header preserved, stripped only on parse)
   - `app.js unchanged (still embeds CSV): OK`

   CSV round-trip detail: extracted the string between boundaries, decoded the literal `\r\n` escapes, parsed with Python's `csv.reader`, got 216 rows (215 data rows + header), row count divisible by 5 and > 0. First date `02-06-2026`, last `31-07-2026`, 43 distinct dates.

2. **Node syntax check**: `node --check data.js` → `SYNTAX OK`.

3. **Node functional test** (sandboxed `vm`, mock `window`/`fetch`, real `lib/utils.js` loaded):
   ```
   NFOD.data keys: availableDates,getParticipantMap,loadMoneyFlow,loadOHLC,parseCSV,rawCSVData
   availableDates count: 43 first: 02-06-2026 last: 31-07-2026
   getParticipantMap keys: Client,DII,FII,Pro,TOTAL
   TOTAL Long Contracts (last date): 21247539
   loadMoneyFlow: {"money":"flow"}
   loadOHLC: {"ohlc":"data"}
   rawCSVData length: 215 divisible by 5: true
   row[0] keys: Client Type,Future Index Long,... (16 headers, spaces stripped)
   ```

   Note: `rawCSVData` length is 215 in node (trailing `\r\n` empty last line skipped by `parseCSV`), 216 total rows with header — matches 43 dates × 5 participants.

## Files changed

- `C:\Users\Surajit Pakira\Documents\NFOD\data.js` (new, 27888 chars)
- `C:\Users\Surajit Pakira\Documents\NFOD\nse_toolkit\fetcher.py` (5 insertions / 5 deletions, all log-string + `appjs_path` edits)
- `C:\Users\Surajit Pakira\Documents\NFOD\app.js` — **untouched** (still embeds old CSV, verified)

## Commit

`ed0bed0` — `refactor(data): move embedded CSV to data.js, retarget updater`
(branch `redesign/overhaul`, 2 files changed, 56 insertions, 5 deletions)

## Self-review notes

- **Byte-for-byte fidelity**: CSV extracted programmatically with Python (`content[start:end]`), not by hand, so no risk of transcription drift. Header trailing spaces (`Future Stock Short       `, `Total Long Contracts      `) confirmed present in raw string and stripped only at parse time by `parseCSV`.
- **Bash heredoc escaping trap** hit during verification: the shell's heredoc strips one backslash level, so testing `csv_str.endswith("\\r\\n")` inline silently tested against real CR/LF. Resolved by moving verification into a script file. Byte-level hexdump (`5c 72 5c 6e`) and the script-file test both confirm the literal `\r\n` escapes are correctly stored in `data.js` — this is the format `update_embedded_csv()` regenerates and `parseCSV` handles.
- **fetcher.py log message fix** went one line past the brief's "one line" — justified because the brief's own expected log text (`Updated data.js embedded CSV`) is impossible without touching those three hardcoded strings. Docstring still says "in app.js" (line 354) — minor, harmless, flagged in concerns.

## Concerns

- `update_embedded_csv()` docstring (fetcher.py line 354) still says "app.js". Cosmetic only; does not affect behavior. Optionally update in a later cleanup.
- `data.js` is not yet referenced by any HTML (script tag lands in Task 4). Until then it's dead code — expected per plan.
- Task 5 replaces `app.js`; the old `app.js` still holds its own copy of the CSV. If Task 5 deletes `app.js`, `FDCP_Data.csv` remains the canonical source and `data.js` stays independent — no coupling risk.
