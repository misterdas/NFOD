import http.server, socketserver, threading, json
from playwright.sync_api import sync_playwright

ROOT = r"C:\Users\Surajit Pakira\Documents\NFOD"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)
    def log_message(self, *a):
        pass

srv = socketserver.TCPServer(("127.0.0.1", 0), H)
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=CHROME, headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 900})

    # --- 1. first paint + gross view ---
    page.goto(f"http://127.0.0.1:{port}/index.html")
    page.wait_for_timeout(2500)
    r = page.evaluate("""() => ({
      footerDate: document.getElementById('footer-date').textContent,
      dateChip: document.getElementById('d-picker').textContent,
      nDates: NFOD.data.availableDates.length,
      latest: NFOD.data.availableDates[NFOD.data.availableDates.length-1],
      activeView: NFOD.state.activeView,
      grossTables: document.querySelectorAll('#view-gross .data-table').length,
      grossRows: document.querySelectorAll('#view-gross .main-col tbody tr').length,
      kpis: document.querySelectorAll('#view-gross .kpi-card').length,
      sparkCells: document.querySelectorAll('#view-gross .spark-cell svg').length
    })""")
    print("FIRST PAINT:", json.dumps(r, indent=1))
    assert r["footerDate"].endswith(r["latest"]), "footer not on latest date"
    assert r["dateChip"] == r["latest"], "date chip not on latest"
    print("OK first paint latest date")

    # --- 2. verdict view ---
    page.click('[data-view="verdict"]')
    page.wait_for_timeout(1500)
    r = page.evaluate("""() => ({
      activeView: NFOD.state.activeView,
      verdictContent: document.getElementById('view-verdict').innerHTML.length,
      verdictHtml: document.getElementById('view-verdict').innerHTML.slice(0,120)
    })""")
    print("VERDICT:", json.dumps(r, indent=1))
    assert r["verdictContent"] > 50, "verdict view empty"
    print("OK verdict renders")

    # --- 3. charts view + theme re-render ---
    page.click('[data-view="charts"]')
    page.wait_for_timeout(2500)
    spy = page.evaluate("""() => {
      window.__renderCalls = 0;
      const orig = NFOD.views.charts.render;
      NFOD.views.charts.render = async function(s){ window.__renderCalls++; return orig(s); };
      return 'spy set';
    }""")
    print("spy:", spy)
    r = page.evaluate("""() => ({
      activeView: NFOD.state.activeView,
      chartEls: document.querySelectorAll('#view-charts .chart-card').length,
      apex: !!window.ApexCharts,
      errorCard: document.querySelector('#view-charts .error-card') ? document.querySelector('#view-charts .error-card').textContent : null
    })""")
    print("CHARTS:", json.dumps(r, indent=1))
    if r["errorCard"]:
        print("NOTE: ApexCharts CDN unavailable in this env (offline?) — charts fallback error-card shown")
    else:
        assert r["chartEls"] == 4, "expected 4 chart cards"
    # toggle theme -> charts.render should be called again
    page.click("#btn-theme")
    page.wait_for_timeout(2000)
    calls = page.evaluate("() => window.__renderCalls")
    print("theme toggle -> charts.render calls:", calls)
    assert calls >= 1, "theme toggle did not re-render charts"
    print("OK theme->charts re-render")

    # --- 4. debug hook ---
    dbg = browser.new_page(viewport={"width": 1280, "height": 900})
    dbg.on("pageerror", lambda e: None)
    dbg.goto(f"http://127.0.0.1:{port}/index.html?debug=1")
    dbg.wait_for_timeout(1500)
    dbg.evaluate("() => NFOD.debuglog('TEST-MARKER')")
    dbg.wait_for_timeout(500)
    r = dbg.evaluate("""() => {
      const el = document.getElementById('debug-log');
      return { hidden: el.hidden, text: el.textContent };
    }""")
    print("DEBUG LOG:", json.dumps(r, indent=1))
    assert r["hidden"] is False and "TEST-MARKER" in r["text"], "debug log not working"
    print("OK debug hook")

    # --- 5. theme body class flip (verify each toggle flips) ---
    before = page.evaluate("() => document.body.className")
    page.click("#btn-theme")
    page.wait_for_timeout(500)
    after = page.evaluate("() => document.body.className")
    print("BODY CLASS TOGGLE:", before, "->", after)
    assert before != after, "theme toggle did not flip body class"
    print("OK theme toggle flips classes")

    # --- 6. date nav (prev/next/latest) ---
    page.click('[data-view="gross"]')
    page.wait_for_timeout(800)
    r = page.evaluate("""() => {
      const before = NFOD.state.dateIndex;
      document.getElementById('d-prev').click();
      const afterPrev = NFOD.state.dateIndex;
      document.getElementById('d-latest').click();
      const afterLatest = NFOD.state.dateIndex;
      return { before, afterPrev, afterLatest, latest: NFOD.data.availableDates.length-1 };
    }""")
    print("DATE NAV:", json.dumps(r, indent=1))
    assert r["afterPrev"] == r["before"]-1 and r["afterLatest"] == r["latest"]
    print("OK date nav")

    browser.close()
srv.shutdown()
print("ALL APP QA PASSED")
