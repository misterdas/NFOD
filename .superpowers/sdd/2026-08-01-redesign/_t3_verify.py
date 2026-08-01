"""Task 3 fix verification: sticky thead + date-chip border."""
import json
from playwright.sync_api import sync_playwright

HTML = "file:///C:/Users/Surajit%20Pakira/Documents/NFOD/.superpowers/sdd/2026-08-01-redesign/_t3_verify.html"
CHROME = "C:/Program Files/Google/Chrome/Application/chrome.exe"

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=CHROME, headless=True)
    pg = b.new_page(viewport={"width": 1200, "height": 900})
    pg.goto(HTML)
    pg.wait_for_timeout(300)

    # --- date-chip border check ---
    chip = pg.evaluate("""() => {
        const el = document.querySelector('.date-chip');
        const cs = getComputedStyle(el);
        return {
            display: cs.display,
            borderTopWidth: cs.borderTopWidth,
            borderTopStyle: cs.borderTopStyle,
            borderTopColor: cs.borderTopColor
        };
    }""")

    # --- sticky thead check ---
    # Measure thead bottom edge relative to wrapper top before scroll, then after scrolling wrapper.
    before = pg.evaluate("""() => {
        const wrap = document.querySelector('.table-scroll');
        const th = document.querySelector('.data-table th');
        return {
            wrapScrollTop: wrap.scrollTop,
            wrapScrollHeight: wrap.scrollHeight,
            wrapClientHeight: wrap.clientHeight,
            thTop: th.getBoundingClientRect().top,
            wrapTop: wrap.getBoundingClientRect().top
        };
    }""")
    pg.evaluate("document.querySelector('.table-scroll').scrollTop = 220;")
    pg.wait_for_timeout(150)
    after = pg.evaluate("""() => {
        const wrap = document.querySelector('.table-scroll');
        const th = document.querySelector('.data-table th');
        return {
            wrapScrollTop: wrap.scrollTop,
            thTop: th.getBoundingClientRect().top,
            wrapTop: wrap.getBoundingClientRect().top
        };
    }""")

    # sticky engaged if thTop stays at wrapTop after scrolling (diff < 2px)
    sticky_before_diff = abs(before["thTop"] - before["wrapTop"])
    sticky_after_diff = abs(after["thTop"] - after["wrapTop"])
    scroll_occurred = after["wrapScrollTop"] > before["wrapScrollTop"]

    result = {
        "date_chip": chip,
        "sticky_before_th_vs_wrap_px": round(sticky_before_diff, 2),
        "sticky_after_th_vs_wrap_px": round(sticky_after_diff, 2),
        "wrapper_scroll_occurred": scroll_occurred,
        "wrapper_scroll_height_vs_client": f"{before['wrapScrollHeight']} vs {before['wrapClientHeight']}",
    }
    print("RESULT_JSON=" + json.dumps(result))

    pg.screenshot(path=".superpowers/sdd/2026-08-01-redesign/_t3_verify.png", full_page=False)
    b.close()
