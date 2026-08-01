import sys, re, datetime
from playwright.sync_api import sync_playwright

INDEX = "file:///C:/Users/Surajit%20Pakira/Documents/NFOD/index.html"
CHROME = "C:/Program Files/Google/Chrome/Application/chrome.exe"

failures = []
console_msgs = []
page_errors = []

def check(cond, label, extra=""):
    if cond:
        print("PASS  " + label + (" " + extra if extra else ""))
    else:
        print("FAIL  " + label + (" " + extra if extra else ""))
        failures.append(label)

def ist_stub(h, m):
    # IST hh:mm -> UTC epoch on 2026-08-03 (Monday, weekday)
    uh, um = h - 5, m - 30
    return """(() => {
      const T = Date.UTC(2026, 7, 3, %d, %d);
      const RealDate = Date;
      window.Date = class extends RealDate {
        constructor(...a){ a.length ? super(...a) : super(T); }
        static now(){ return T; }
      };
    })();""" % (uh, um)

# (IST hour, IST min, expected label, expected live flag)
IST_CASES = [
    (8, 59, "CLOSED", False),
    (9, 5, "PRE-MARKET", False),
    (9, 20, "LIVE", True),
    (15, 30, "LIVE", True),
    (15, 31, "CLOSED", False),
]

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=CHROME, headless=True)

    # ---------- Section A: IST boundary windows (deterministic) ----------
    for h, m, exp_label, exp_live in IST_CASES:
        page = browser.new_page()
        errs = []
        page.on("pageerror", lambda e, errs=errs: errs.append(str(e)))
        page.add_init_script(ist_stub(h, m))
        page.goto(INDEX)
        # wait >1s so the 1s clock interval has fired at least once (fixed Date -> stable text)
        page.wait_for_timeout(1300)
        pill = page.locator(".status-pill").inner_text()
        live = page.locator(".status-pill").evaluate("(el) => el.classList.contains('live')")
        clock = page.locator("#ist-clock").inner_text()
        ok = (exp_label in pill) and (live == exp_live)
        check(ok, "IST %02d:%02d -> %s live=%s" % (h, m, exp_label, exp_live),
              extra="pill=%r live=%s" % (pill, live))
        check(clock == "%02d:%02d IST" % (h, m), "IST %02d:%02d clock text" % (h, m), extra=clock)
        # no duplicate-declaration on any boundary load
        redecl = [e for e in errs if "already been declared" in e]
        check(len(redecl) == 0, "IST %02d:%02d no redeclare error" % (h, m))
        page.close()

    # ---------- Sections B/C/D: functional page (real clock) ----------
    page = browser.new_page()
    page.on("console", lambda m: console_msgs.append((m.type, m.text)))
    page.on("pageerror", lambda e: page_errors.append(str(e)))
    page.goto(INDEX)
    page.wait_for_timeout(600)

    # B: NFOD.switchView exported + callable from console
    check(page.evaluate("() => typeof NFOD.switchView") == "function", "NFOD.switchView is function")
    check(page.evaluate("() => NFOD.switchView.name") == "switchView", "NFOD.switchView named 'switchView'")
    page.evaluate("() => NFOD.switchView('verdict')")
    check(page.evaluate("() => NFOD.state.activeView") == "verdict", "console switchView -> activeView=verdict")
    check(page.locator("#view-verdict").evaluate("(el) => el.classList.contains('active')"), "console switchView -> #view-verdict active")
    check(page.locator("#view-gross").evaluate("(el) => !el.classList.contains('active')"), "console switchView -> #view-gross inactive")
    check(page.locator("button.tab-btn[data-view=verdict]").evaluate("(el) => el.classList.contains('active')"), "console switchView -> verdict tab active")
    page.evaluate("() => NFOD.switchView('charts')")
    check(page.locator("#view-charts").evaluate("(el) => el.classList.contains('active')"), "console switchView charts -> active")
    # tab button click still routes through NFOD.switchView
    page.click("button[data-view=gross]")
    check(page.evaluate("() => NFOD.state.activeView") == "gross", "tab click still switches (bindTabs via NFOD.switchView)")

    # C: no duplicate-declaration error
    all_errs = console_msgs + [("pageerror", e) for e in page_errors]
    redeclare = [e for _, e in all_errs if "already been declared" in e]
    check(len(redeclare) == 0, "no duplicate-declaration console error",
          extra=("REDECLARE: %r" % redeclare) if redeclare else "")

    # C: date nav still works
    dates = page.evaluate("() => NFOD.state.dates")
    check(len(dates) == 43 and dates[0] == "02-06-2026", "dates loaded", extra="n=%d" % len(dates))
    page.click("#d-next")
    check(page.evaluate("() => NFOD.state.dateIndex") == 1, "next advances")
    check(page.locator("#footer-date").inner_text() == "Date: " + dates[1], "footer-date updated")
    page.click("#d-latest")
    check(page.evaluate("() => NFOD.state.dateIndex") == len(dates) - 1, "latest jumps")
    page.click("#d-next")
    check(page.evaluate("() => NFOD.state.dateIndex") == len(dates) - 1, "next clamps at last")

    # C: theme toggle still works
    page.click("#btn-theme")
    check(page.evaluate("() => document.body.classList.contains('theme-light')"), "theme -> light")
    check(page.evaluate("() => NFOD.state.theme") == "light", "state.theme=light")
    page.click("#btn-theme")
    check(page.evaluate("() => document.body.classList.contains('theme-dark')"), "theme -> dark")

    # C: clock ticks (stub Date advance 61s)
    page.evaluate("""
        (() => {
            const RealDate = Date; let offset = 0;
            window.__adv = (ms) => { offset = ms; };
            window.Date = class extends RealDate {
                constructor(...a){ a.length ? super(...a) : super(RealDate.now() + offset); }
                static now(){ return RealDate.now() + offset; }
            };
        })();
    """)
    c0 = page.locator("#ist-clock").inner_text()
    page.evaluate("() => window.__adv(61000)")
    page.wait_for_timeout(1500)
    c1 = page.locator("#ist-clock").inner_text()
    check(c1 != c0, "clock ticks after 61s advance", extra="%s -> %s" % (c0, c1))
    check(re.match(r"^\d{2}:\d{2} IST$", c1), "clock format", extra=c1)

    # C: d-picker still throws createDatePicker (expected until Task 6), app survives
    # park mid-range first so #d-next advances (currently clamped at last)
    page.click("#d-prev"); page.click("#d-prev")
    check(page.evaluate("() => NFOD.state.dateIndex") == 40, "parked at 40 before picker test",
          extra="dateIndex=%d" % page.evaluate("() => NFOD.state.dateIndex"))
    page.click("#d-picker")
    page.wait_for_timeout(300)
    picker_err = [e for e in page_errors if "createDatePicker" in e]
    check(len(picker_err) > 0, "d-picker throws createDatePicker (expected, Task 6)",
          extra=("err=%r" % picker_err[:1]) if picker_err else "")
    idx_before = page.evaluate("() => NFOD.state.dateIndex")
    page.click("#d-next")
    idx_after = page.evaluate("() => NFOD.state.dateIndex")
    check(idx_after == idx_before + 1, "app functional after d-picker throw",
          extra="dateIndex %d -> %d" % (idx_before, idx_after))

    browser.close()

print("\nRESULT: %s" % ("ALL PASS" if not failures else "FAILURES: %s" % failures))
sys.exit(1 if failures else 0)
