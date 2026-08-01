"""Task 11 verification: verdict view reads NESTED schema (precedence over flat).
Proof: craft data where nested value differs from flat — rendered value must be nested.
Uses local HTTP server (file:// fetch is blocked by Chrome)."""
import asyncio, http.server, json, os, threading
from playwright.async_api import async_playwright

ROOT = r"C:\Users\Surajit Pakira\Documents\NFOD"
DATA = os.path.join(ROOT, "docs", "money_flow_data.json")
DATA_BAK = DATA + ".bak"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
URL = "http://127.0.0.1:8123/index.html"
SHOT = os.path.join(ROOT, ".superpowers", "sdd", "2026-08-01-redesign", "t11_verdict.png")

class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass

def start_server():
    os.chdir(ROOT)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 8123), Quiet)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv

def bump(d):
    """Nested values get markers; flat stance keys nulled so the stance panel's
    `??` fallback must render from the nested schema (proves nested keys match)."""
    ps = d["participant_summary"]
    # banner/rolls/conviction/divergence/breadth read nested-first — mark them
    d["verdict"]["score"] = 12345
    d["verdict"]["bias"] = "NESTED BIAS MARKER"
    d["verdict"]["actionDesc"] = "NESTED ACTION DESC MARKER"
    d["retail"]["confirmationScore"] = 4242
    # distinctive nested stance values
    p = d["participants"]
    p["fii"]["options"]["ce"]["netShort"] = 9876
    p["fii"]["options"]["pe"]["netShort"] = 5555
    p["fii"]["futures"]["net"] = 111111
    p["pro"]["options"]["ce"]["netShort"] = 6666
    p["pro"]["options"]["pe"]["netShort"] = 7777
    p["client"]["options"]["ce"]["netBuy"] = 8888
    p["dii"]["options"]["ce"]["netShort"] = 9999
    p["dii"]["options"]["pe"]["netShort"] = 10101
    p["dii"]["futures"]["net"] = 121212
    # null the flat keys verdict.js stance rows read → nested fallback must win
    for k in ["fii_ce_net_short_change", "fii_pe_net_short_change", "fii_fut_net_change",
              "pro_ce_net_short_change", "pro_pe_net_short_change", "client_ce_net_buy",
              "dii_ce_net_short_change", "dii_pe_net_short_change", "dii_fut_net_change"]:
        ps[k] = None
    return d

async def run():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(executable_path=CHROME, headless=True)
        page = await browser.new_page()
        errors, notfound = [], []
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("response", lambda r: notfound.append(r.url) if r.status == 404 else None)
        await page.goto(URL, wait_until="networkidle")
        await page.wait_for_timeout(500)
        await page.click('.tab-btn[data-view="verdict"]')
        await page.wait_for_timeout(800)

        checks = {}

        banner = await page.query_selector(".verdict-banner")
        checks["banner"] = banner is not None
        if banner:
            badge = await page.text_content(".verdict-banner .badge")
            gauge = await page.text_content(".verdict-banner .verdict-gauge")
            desc = await page.text_content(".verdict-banner .banner-desc")
            checks["badge_nested"] = "NESTED BIAS MARKER" in (badge or "")
            checks["gauge_nested"] = "12345" in (gauge or "")
            checks["desc_nested"] = "NESTED ACTION DESC MARKER" in (desc or "")

        checks["roll_cards"] = await page.locator(".roll-card").count()
        checks["fii_row"] = await page.locator(".section-label.fii").count()
        checks["stat_rows"] = await page.locator(".stat-row").count()
        # stance rows (0..8) must show nested markers, since flat keys are null
        rows = [ (await page.locator(".stat-row").nth(i).text_content()).replace("\n", " ")
                 for i in range(9) ]
        expected = {
            0: ("9876", "FII Call Options Stance"),
            1: ("5555", "FII Put Options Stance"),
            2: ("111111", "FII Futures Net Shift"),
            3: ("6666", "Pro Call Net-Short"),
            4: ("7777", "Pro Put Net-Short"),
            5: ("8888", "Retail Net Calls"),
            6: ("9999", "DII Call Shift"),
            7: ("10101", "DII Put Shift"),
            8: ("121212", "DII Futures Net"),
        }
        norm = lambda s: s.replace(",", "").replace(" ", "")
        checks["stance_nested"] = all(norm(exp) in norm(rows[i]) for i, (exp, _) in expected.items())
        if not checks["stance_nested"]:
            for i, (exp, label) in expected.items():
                if norm(exp) not in norm(rows[i]):
                    print(f"   stance row {i} ({label}): expected {exp} in {rows[i]!r}")

        checks["conv_tabs"] = await page.locator(".conv-tabs .tab-btn").count()
        checks["conv_body_rows"] = await page.locator("#conv-body tr").count()
        checks["divg_items"] = await page.locator(".divg-item").count()
        checks["breadth_cols"] = await page.locator(".breadth-col").count()
        checks["breadth_rows"] = await page.locator(".breadth-col .data-table tr").count()

        await page.screenshot(path=SHOT, full_page=True)
        await browser.close()

    real_errors = [e for e in errors if "charts.js" not in e and "Failed to load resource" not in e]
    bad_notfound = [u for u in notfound if "charts.js" not in u and "favicon" not in u]
    print("=== CHECKS ===")
    for k, v in checks.items():
        print(f"{k}: {v}")
    print("=== CONSOLE ERRORS (excluding charts.js 404) ===")
    print("\n".join(real_errors) if real_errors else "NONE")
    print("=== 404 NOT FOUND (excluding charts.js) ===")
    print("\n".join(bad_notfound) if bad_notfound else "NONE")
    ok = all([
        checks["banner"], checks["badge_nested"], checks["gauge_nested"], checks["desc_nested"],
        checks["roll_cards"] >= 3, checks["fii_row"] >= 1, checks["stat_rows"] >= 9,
        checks["stance_nested"],
        checks["conv_tabs"] >= 2, checks["conv_body_rows"] >= 1,
        checks["divg_items"] >= 1, checks["breadth_cols"] == 4,
        not real_errors, not bad_notfound,
    ])
    print("=== VERDICT ===")
    print("PASS — NESTED PATH WINS" if ok else "FAIL")

async def main():
    srv = start_server()
    with open(DATA, "r", encoding="utf-8") as f:
        d = json.load(f)
    shutil_copy = __import__("shutil")
    shutil_copy.copy(DATA, DATA_BAK)
    try:
        with open(DATA, "w", encoding="utf-8") as f:
            json.dump(bump(d), f)
        await run()
    finally:
        srv.shutdown()
        shutil_copy.move(DATA_BAK, DATA)

asyncio.run(main())
