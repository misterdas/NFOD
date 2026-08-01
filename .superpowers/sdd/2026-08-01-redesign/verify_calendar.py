import re
from pathlib import Path
from playwright.sync_api import sync_playwright

URL = Path(r"C:\Users\Surajit Pakira\Documents\NFOD\index.html").as_uri()
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

results = []
def check(name, cond, extra=""):
    results.append((name, bool(cond), extra))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{extra}]" if extra else ""))

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=CHROME, headless=True)
    pg = b.new_page()
    pg.on("console", lambda m: print(f"  console[{m.type}]: {m.text[:120]}"))
    pg.goto(URL)
    pg.wait_for_selector("#d-picker", timeout=15000)
    dates = pg.evaluate("NFOD.data.availableDates")
    n = len(dates)
    check("data loaded", n > 0, f"n={n}")
    check("dates sorted DD-MM-YYYY", all(re.fullmatch(r"\d{2}-\d{2}-\d{4}", d) for d in dates))
    first, last = dates[0], dates[-1]
    check("first/last", first < last, f"{first} .. {last}")

    # open popover
    pg.click("#d-picker")
    pg.wait_for_selector(".cal-popover", timeout=5000)
    lbl = pg.text_content(".cal-label")
    now = pg.evaluate("new Date()")
    expect_lbl = pg.evaluate("new Date().toLocaleString('en-IN', {month:'long', year:'numeric'})")
    check("popover opens, label=current month", lbl == expect_lbl, f"{lbl!r}")

    # prev month navigation -> July 2026 has trading days
    pg.click("#cal-prev")
    pg.wait_for_function("document.querySelector('.cal-label').textContent.includes('July')")
    trad = pg.evaluate("document.querySelectorAll('.cal-cell.tradable').length")
    dimd = pg.evaluate("document.querySelectorAll('.cal-cell.dim[disabled]').length")
    check("prev month works", trad > 0, f"tradable={trad}")
    check("non-trading days dim/disabled", dimd > 0, f"dim={dimd}")

    # round-trip: click day 28 in July -> chip should be 28-07-2026
    pg.click("button.cal-cell.tradable:text-is('28')")
    pg.wait_for_selector(".cal-popover", state="detached")
    chip = pg.text_content("#d-picker").strip()
    idx = pg.evaluate("NFOD.state.dateIndex")
    check("cell click round-trip -> 28-07-2026", chip == "28-07-2026" and dates[idx] == "28-07-2026",
          f"chip={chip} idx={idx}")
    foot = pg.text_content("#footer-date")
    check("footer date updated", "28-07-2026" in foot, foot)

    # Latest preset
    pg.click("#d-picker"); pg.wait_for_selector(".cal-popover")
    pg.click('[data-preset="latest"]')
    pg.wait_for_selector(".cal-popover", state="detached")
    chip = pg.text_content("#d-picker").strip()
    check("Latest preset -> last date", chip == last, f"chip={chip} last={last}")

    # Week Ago preset (current idx = n-1 -> n-6)
    pg.click("#d-picker"); pg.wait_for_selector(".cal-popover")
    pg.click('[data-preset="week"]')
    pg.wait_for_selector(".cal-popover", state="detached")
    chip = pg.text_content("#d-picker").strip()
    exp = dates[max(0, n - 1 - 5)]
    check("Week Ago preset -> -5", chip == exp, f"chip={chip} exp={exp}")

    # Month Expiry preset
    pg.click("#d-picker"); pg.wait_for_selector(".cal-popover")
    pg.click('[data-preset="expiry"]')
    pg.wait_for_selector(".cal-popover", state="detached")
    chip = pg.text_content("#d-picker").strip()
    check("Month Expiry preset -> trading date", chip in dates, f"chip={chip}")
    expi = pg.evaluate("dates => {let best=0,bd=1e9;dates.forEach((d,i)=>{const df=NFOD.utils.daysToMonthlyExpiry(d);if(df===null)return;const di=Math.abs(df);if(di<bd){bd=di;best=i;}});return dates[best];}", dates)
    check("Month Expiry preset -> correct date", chip == expi, f"chip={chip} exp={expi}")

    # next month navigation
    pg.click("#d-picker"); pg.wait_for_selector(".cal-popover")
    pg.click("#cal-next"); pg.click("#cal-next")
    lbl = pg.text_content(".cal-label")
    check("next month works", "October 2026" in lbl, lbl)

    # arrow-key month navigation (ArrowLeft -> September, ArrowRight -> October)
    pg.click("#d-picker"); pg.wait_for_selector(".cal-popover")
    pg.keyboard.press("ArrowLeft")
    pg.wait_for_function("document.querySelector('.cal-label').textContent.includes('July 2026')")
    check("ArrowLeft -> previous month", True, pg.text_content(".cal-label"))
    pg.keyboard.press("ArrowRight")
    pg.wait_for_function("document.querySelector('.cal-label').textContent.includes('August 2026')")
    check("ArrowRight -> next month", True, pg.text_content(".cal-label"))
    # stale keydown handler must NOT linger after arrow nav (popover stays open)
    pg.wait_for_selector(".cal-popover", timeout=2000)
    check("arrow nav keeps popover open", True)

    # outside click closes
    pg.click("#d-picker"); pg.wait_for_selector(".cal-popover")
    pg.click("body", position={"x": 5, "y": 5})
    pg.wait_for_selector(".cal-popover", state="detached")
    check("outside click closes", True)
    # keydown cleanup: after outside-close, stale handler must not linger/throw
    pg.keyboard.press("ArrowRight"); pg.keyboard.press("Escape")
    pg.wait_for_timeout(150)
    check("no stale keydown after outside-close", not pg.evaluate("!!document.querySelector('.cal-popover')"))

    # Esc closes
    pg.click("#d-picker"); pg.wait_for_selector(".cal-popover")
    pg.keyboard.press("Escape")
    pg.wait_for_selector(".cal-popover", state="detached")
    check("Esc closes", True)

    # dimmed cell click does not select (disabled attr: force click, events never fire)
    pg.click("#d-picker"); pg.wait_for_selector(".cal-popover")
    pg.click("#cal-prev"); pg.wait_for_selector(".cal-popover")
    before = pg.text_content("#d-picker").strip()
    pg.click("button.cal-cell.dim[disabled]", force=True)
    pg.wait_for_timeout(200)
    still = pg.evaluate("!!document.querySelector('.cal-popover')")
    after = pg.text_content("#d-picker").strip()
    check("dimmed cell not selectable", still and before == after, f"chip={after}")

    b.close()

fails = [r for r in results if not r[1]]
print("\n==== SUMMARY ====")
print(f"{len(results)-len(fails)}/{len(results)} passed")
if fails:
    print("FAILURES:", ", ".join(r[0] for r in fails))
    raise SystemExit(1)
