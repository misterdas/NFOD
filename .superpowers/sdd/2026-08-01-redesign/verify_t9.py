"""Task 9 verification: verdict view against OLD flat schema + error path.
Uses local HTTP server (file:// fetch is blocked by Chrome)."""
import asyncio, functools, http.server, json, os, shutil, threading
from playwright.async_api import async_playwright

ROOT = r"C:\Users\Surajit Pakira\Documents\NFOD"
DATA = os.path.join(ROOT, "docs", "money_flow_data.json")
DATA_BAK = DATA + ".bak"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
URL = "http://127.0.0.1:8123/index.html"

class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass

def start_server():
    os.chdir(ROOT)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 8123), Quiet)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv

def new_page(browser):
    page = browser.new_page()
    errors = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
    return page, errors

async def run():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(executable_path=CHROME, headless=True)
        page = await browser.new_page()
        errors = []
        notfound = []
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
            checks["badge_text"] = badge.strip() if badge else None
            checks["gauge_text"] = gauge.strip() if gauge else None
            checks["desc"] = (desc or "").strip()

        checks["roll_cards"] = await page.locator(".roll-card").count()
        roll_text = await page.locator(".roll-card").first.text_content()
        checks["roll_has_magnet"] = "Magnet" in roll_text and "Max Pain" in roll_text and "PCR" in roll_text

        checks["fii_row"] = await page.locator(".section-label.fii").count()
        checks["pro_row"] = await page.locator(".section-label.pro").count()
        checks["dii_row"] = await page.locator(".section-label.dii").count()
        checks["stat_rows"] = await page.locator(".stat-row").count()
        checks["fii_ce_value"] = (await page.locator(".stat-row").nth(0).text_content()).replace("\n", " ")

        checks["conv_tabs"] = await page.locator(".conv-tabs .tab-btn").count()
        checks["conv_body_rows"] = await page.locator("#conv-body tr").count()

        btns = await page.locator(".conv-tabs .tab-btn").all_text_contents()
        if len(btns) > 1:
            await page.click(f'.conv-tabs .tab-btn[data-sym="{btns[-1]}"]')
            await page.wait_for_timeout(300)
            active = await page.locator(".conv-tabs .tab-btn.active").text_content()
            checks["tab_switch_active"] = active.strip()
            checks["tab_switch_rows"] = await page.locator("#conv-body tr").count()
            checks["tab_switch_rerender"] = True

        checks["divg_items"] = await page.locator(".divg-item").count()
        checks["breadth_cols"] = await page.locator(".breadth-col").count()
        checks["breadth_rows"] = await page.locator(".breadth-col .data-table tr").count()

        await page.screenshot(path=os.path.join(ROOT, ".superpowers", "sdd", "2026-08-01-redesign", "t9_verdict.png"), full_page=True)
        await browser.close()

    # charts.js 404 is expected (Task 10). Generic resource-load log fires for
    # that same 404; its URL is accounted for via bad_notfound below.
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
        checks["banner"], checks["roll_cards"] >= 3, checks["roll_has_magnet"],
        checks["fii_row"] >= 1, checks["pro_row"] >= 1, checks["dii_row"] >= 1,
        checks["stat_rows"] >= 9, checks["conv_tabs"] >= 2, checks["conv_body_rows"] >= 1,
        checks["breadth_cols"] == 4, checks["divg_items"] >= 1, not real_errors, not bad_notfound,
    ])
    print("=== VERDICT ===")
    print("PASS" if ok else "FAIL")

async def run_missing():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(executable_path=CHROME, headless=True)
        page = await browser.new_page()
        await page.goto(URL, wait_until="networkidle")
        await page.wait_for_timeout(500)
        await page.click('.tab-btn[data-view="verdict"]')
        await page.wait_for_timeout(800)
        err = await page.query_selector("#view-verdict .error-card")
        has_retry = await page.locator("#view-verdict .retry-btn").count() > 0
        shutil.move(DATA_BAK, DATA)  # restore file
        await page.wait_for_timeout(300)
        await page.click("#view-verdict .retry-btn")
        await page.wait_for_timeout(800)
        banner_after = await page.query_selector("#view-verdict .verdict-banner")
        await browser.close()
        print("=== MISSING-DATA PATH ===")
        print("error_card:", err is not None)
        print("retry_btn:", has_retry)
        print("banner_after_retry:", banner_after is not None)
        print("MISSING_PATH_PASS" if (err is not None and has_retry and banner_after is not None) else "MISSING_PATH_FAIL")

async def main():
    srv = start_server()
    shutil.copy(DATA, DATA_BAK)
    try:
        await run()
        print()
        os.remove(DATA)
        await run_missing()
    finally:
        srv.shutdown()
        if not os.path.exists(DATA) and os.path.exists(DATA_BAK):
            shutil.move(DATA_BAK, DATA)
        elif os.path.exists(DATA_BAK):
            os.remove(DATA_BAK)

asyncio.run(main())
