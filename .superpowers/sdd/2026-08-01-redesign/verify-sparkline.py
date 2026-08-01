import sys, json
from playwright.sync_api import sync_playwright

URL = "file:///C:/Users/Surajit Pakira/Documents/NFOD/.superpowers/sdd/2026-08-01-redesign/verify-sparkline.html"

with sync_playwright() as p:
    b = p.chromium.launch(executable_path="C:/Program Files/Google/Chrome/Application/chrome.exe")
    pg = b.new_page()
    errs = []
    pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL)
    pg.wait_for_function("window.__RESULTS !== undefined && Object.keys(window.__RESULTS).length >= 10")
    results = pg.evaluate("window.__RESULTS")
    svg = pg.eval_on_selector("svg polyline", "el => el.getAttribute('points')")
    b.close()

ok = all(results.values())
print("RESULTS:", json.dumps(results, indent=2))
print("CONSOLE_ERRORS:", json.dumps(errs))
print("FIVE-PT POLYLINE:", svg)
print("PASS" if ok and not errs else "FAIL")
sys.exit(0 if ok and not errs else 1)
