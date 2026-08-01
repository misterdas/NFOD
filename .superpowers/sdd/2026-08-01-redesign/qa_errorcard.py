import http.server, socketserver, threading, json, os
from playwright.sync_api import sync_playwright

ROOT = r"C:\Users\Surajit Pakira\Documents\NFOD"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
MF = os.path.join(ROOT, "docs", "money_flow_data.json")

class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)
    def log_message(self, *a):
        pass

srv = socketserver.TCPServer(("127.0.0.1", 0), H)
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=CHROME, headless=True)

    # 404 path in fresh context (clean HTTP cache)
    os.rename(MF, MF + ".bak")
    try:
        ctx = b.new_context()
        pg = ctx.new_page()
        pg.goto(f"http://127.0.0.1:{port}/index.html")
        pg.wait_for_timeout(2000)
        r = pg.evaluate("""() => ({
          takeaways: document.querySelectorAll('#view-gross .takeaway-item').length,
          noCrash: !!document.getElementById('view-gross').innerHTML,
          mf: null
        })""")
        print("MF 404 -> takeaways items:", r["takeaways"], "| view rendered:", r["noCrash"])
        assert r["takeaways"] == 0, "expected no takeaways when money_flow 404s"
        assert r["noCrash"], "view broke on 404"
        print("OK graceful 404")
        ctx.close()
    finally:
        os.rename(MF + ".bak", MF)

    # restored path in fresh context
    ctx = b.new_context()
    pg = ctx.new_page()
    pg.goto(f"http://127.0.0.1:{port}/index.html")
    pg.wait_for_timeout(2500)
    r = pg.evaluate("() => document.querySelectorAll('#view-gross .takeaway-item').length")
    print("Restored -> takeaways items:", r)
    assert r > 0, "takeaways missing after restore"
    print("OK retry/restore")
    ctx.close()
    b.close()
srv.shutdown()
print("ERROR CARD + RETRY PASSED")
