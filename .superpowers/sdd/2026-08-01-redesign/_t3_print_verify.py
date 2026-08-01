"""Task 3 print fix verification: .table-scroll must not clip in print."""
import json
from playwright.sync_api import sync_playwright

HTML = "file:///C:/Users/Surajit%20Pakira/Documents/NFOD/.superpowers/sdd/2026-08-01-redesign/_t3_verify.html"
CHROME = "C:/Program Files/Google/Chrome/Application/chrome.exe"

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=CHROME, headless=True)
    pg = b.new_page(viewport={"width": 1200, "height": 900})

    # SCREEN baseline (before fix the wrapper clips)
    pg.goto(HTML)
    pg.wait_for_timeout(200)
    scr = pg.evaluate("""() => {
        const w = document.querySelector('.table-scroll');
        const cs = getComputedStyle(w);
        return {maxHeight: cs.maxHeight, overflowY: cs.overflowY,
                clientHeight: w.clientHeight, scrollHeight: w.scrollHeight};
    }""")

    # PRINT media
    pg.emulate_media(media="print")
    pg.wait_for_timeout(200)
    prn = pg.evaluate("""() => {
        const w = document.querySelector('.table-scroll');
        const cs = getComputedStyle(w);
        const th = document.querySelector('.data-table th');
        const thCS = getComputedStyle(th);
        return {maxHeight: cs.maxHeight, overflowY: cs.overflowY,
                clientHeight: w.clientHeight, scrollHeight: w.scrollHeight,
                thPosition: thCS.position};
    }""")

    result = {"screen": scr, "print": prn}
    print("RESULT_JSON=" + json.dumps(result))
    b.close()
