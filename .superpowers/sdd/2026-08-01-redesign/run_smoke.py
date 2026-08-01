import http.server, socketserver, threading, sys
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

lines = []
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=CHROME, headless=True)
    page = browser.new_page()
    page.on("console", lambda m: lines.append(m.text))
    page.on("pageerror", lambda e: lines.append("PAGEERROR: " + str(e)))
    page.goto(f"http://127.0.0.1:{port}/test/smoke.html")
    page.wait_for_timeout(2000)
    browser.close()

print("\n".join(lines))
srv.shutdown()
