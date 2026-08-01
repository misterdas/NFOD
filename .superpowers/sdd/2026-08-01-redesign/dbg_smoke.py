import http.server, socketserver, threading
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
    page = browser.new_page()
    page.on("console", lambda m: print(m.text))
    page.on("pageerror", lambda e: print("PAGEERROR:", e))
    page.goto(f"http://127.0.0.1:{port}/test/smoke.html")
    page.wait_for_timeout(1500)
    info = page.evaluate("""() => {
      const map = NFOD.data.getParticipantMap(NFOD.data.availableDates[NFOD.data.availableDates.length-1]);
      const tables = document.querySelectorAll('#view-gross .data-table');
      return {
        mapKeys: Object.keys(map),
        numTables: tables.length,
        rowsPerTable: Array.from(tables).map(t => t.querySelectorAll('tbody tr').length),
        nDates: NFOD.data.availableDates.length,
        lastDate: NFOD.data.availableDates[NFOD.data.availableDates.length-1],
        firstParticipants: Array.from(tables[0].querySelectorAll('tbody tr .participant')).map(x=>x.textContent)
      };
    }""")
    import json
    print(json.dumps(info, indent=1))
    browser.close()
srv.shutdown()
