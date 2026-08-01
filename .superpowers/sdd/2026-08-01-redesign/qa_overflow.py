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
    b = p.chromium.launch(executable_path=CHROME, headless=True)
    for width, height, label in [(390, 844, "mobile"), (1280, 900, "desktop")]:
        for view in ["gross", "verdict", "charts"]:
            ctx = b.new_context(viewport={"width": width, "height": height})
            pg = ctx.new_page()
            pg.goto(f"http://127.0.0.1:{port}/index.html")
            pg.wait_for_timeout(1800)
            pg.click(f'[data-view="{view}"]')
            pg.wait_for_timeout(2500 if view == "charts" else 1200)
            r = pg.evaluate("""() => ({
              bodyW: document.body.scrollWidth, vw: window.innerWidth,
              active: document.querySelector('.view.active') ? document.querySelector('.view.active').id : null
            })""")
            ok = r["bodyW"] <= r["vw"] + 1
            print(f"{label} {view}: bodyW={r['bodyW']} vw={r['vw']} {'OK' if ok else 'OVERFLOW'}")
            assert ok, f"{label} {view} overflows"
            ctx.close()
    b.close()
srv.shutdown()
print("OVERFLOW SWEEP PASSED")
