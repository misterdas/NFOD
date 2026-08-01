#!/usr/bin/env python3
"""Task 8 verification: views/gross.js on real index.html via headless Chrome."""
import csv, json, re, subprocess, sys
from playwright.sync_api import sync_playwright

ROOT = r"C:\Users\Surajit Pakira\Documents\NFOD"
URL = "http://127.0.0.1:8123/index.html"

def parse_num(s):
    s = s.replace(",", "").replace("+", "").strip()
    if s in ("", "-", "–", "—"):
        return None
    try:
        return int(s)
    except ValueError:
        return None

def main():
    results = []
    def check(name, cond, detail=""):
        results.append((name, cond, detail))
        print(("PASS  " if cond else "FAIL  ") + name + (("  " + detail) if detail else ""))

    # ---- expected values from FDCP_Data.csv (external source) ----
    rows = list(csv.DictReader(open(ROOT + r"\FDCP_Data.csv", encoding="utf-8")))
    def row(date, ptype):
        for r in rows:
            if r["Client Type"].strip() == ptype and r["Date"].strip() == date:
                return {k.strip(): (int(v) if v.strip().isdigit() else v.strip()) for k, v in r.items()}
        return None
    def net_delta(date, ptype, long_col, short_col):
        cur, prv = row(date, ptype), row("30-07-2026", ptype)
        if not cur or not prv:
            return None
        return (cur[long_col] - prv[long_col]) - (cur[short_col] - prv[short_col])
    exp_fii_fut = net_delta("31-07-2026", "FII", "Future Index Long", "Future Index Short")
    exp_cl_calls = net_delta("31-07-2026", "Client", "Option Index Call Long", "Option Index Call Short")
    exp_pro_calls = net_delta("31-07-2026", "Pro", "Option Index Call Long", "Option Index Call Short")
    exp_pro_puts = net_delta("31-07-2026", "Pro", "Option Index Put Long", "Option Index Put Short")
    exp_pro_puts = (row("31-07-2026","Pro")["Option Index Put Short"]-row("30-07-2026","Pro")["Option Index Put Short"]) - \
                   (row("31-07-2026","Pro")["Option Index Put Long"]-row("30-07-2026","Pro")["Option Index Put Long"])
    exp_bias = (exp_fii_fut or 0) + (exp_pro_calls or 0) + (exp_pro_puts or 0)
    exp_bias_txt = "BULLISH" if exp_bias > 20000 else ("BEARISH" if exp_bias < -20000 else "NEUTRAL / MIXED")
    print(f"expected: fii_fut={exp_fii_fut} cl_calls={exp_cl_calls} pro_calls={exp_pro_calls} "
          f"pro_puts={exp_pro_puts} bias={exp_bias} bias_txt={exp_bias_txt}")

    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=r"C:/Program Files/Google/Chrome/Application/chrome.exe",
                                    headless=True)
        ctx = browser.new_context(accept_downloads=True)
        page = ctx.new_page()
        console_errs, page_errs, failed_reqs = [], [], []
        page.on("console", lambda m: console_errs.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: page_errs.append(str(e)))
        page.on("requestfailed", lambda r: failed_reqs.append(r.url))
        page.goto(URL, wait_until="networkidle", timeout=30000)
        page.wait_for_selector(".takeaway-item", timeout=15000)
        page.wait_for_timeout(300)
        # app default dateIndex=0 (oldest); navigate to latest for value checks
        page.click("#d-latest")
        page.wait_for_timeout(300)
        chip0 = page.query_selector("#d-picker").inner_text()
        check("initial view on latest date", chip0 == "31-07-2026", chip0)

        # --- structure: 4 KPI cards, 6 tables x 4 rows, sparkline column ---
        kpis = page.query_selector_all("#view-gross .kpi-bar .kpi-card")
        check("4 KPI cards", len(kpis) == 4, f"got {len(kpis)}")
        tables = page.query_selector_all("#view-gross .main-col .instrument-block")
        check("6 instrument tables", len(tables) == 6, f"got {len(tables)}")
        tbody_rows = [page.query_selector_all(t.query_selector("tbody")._impl_obj.selector + "") for t in tables] if False else None
        row_counts = []
        for t in tables:
            tbody = t.query_selector("tbody")
            row_counts.append(len(tbody.query_selector_all("tr")))
        check("each table has 4 participant rows", row_counts == [4]*6, str(row_counts))
        spark_cells = page.query_selector_all("#view-gross .spark-cell svg.sparkline")
        check("sparkline column rendered (24 svgs)", len(spark_cells) == 24, f"got {len(spark_cells)}")
        rail_cards = page.query_selector_all("#view-gross .right-rail .rail-card")
        check("right rail has 4 participant cards", len(rail_cards) == 4, f"got {len(rail_cards)}")
        tw = page.query_selector("#view-gross .takeaways")
        check("takeaways async loaded", tw is not None)
        takeaway_text = tw.inner_text() if tw else ""
        check("takeaway shows session date", "31-07-2026" in takeaway_text, takeaway_text.splitlines()[0] if takeaway_text else "")

        # --- KPI value cross-check vs FDCP_Data.csv ---
        def kpi_val(i):
            el = kpis[i].query_selector(".kpi-value")
            return parse_num(el.inner_text())
        got_fii, got_cl, got_pro = kpi_val(0), kpi_val(1), kpi_val(2)
        check("KPI1 FII Index Futures net matches", got_fii == exp_fii_fut, f"{got_fii} vs {exp_fii_fut}")
        check("KPI2 Client Index Calls net matches", got_cl == exp_cl_calls, f"{got_cl} vs {exp_cl_calls}")
        check("KPI3 Pro Index Calls net matches", got_pro == exp_pro_calls, f"{got_pro} vs {exp_pro_calls}")
        bias_val = kpis[3].query_selector(".kpi-value").inner_text().strip()
        check("bias text matches", bias_val == exp_bias_txt, f"{bias_val} vs {exp_bias_txt}")
        bias_score = parse_num(kpis[3].query_selector(".kpi-sub").inner_text().replace("Score ", ""))
        check("bias score matches", bias_score == exp_bias, f"{bias_score} vs {exp_bias}")
        cls = kpis[3].query_selector(".kpi-value").get_attribute("class")
        check("bias card sign class", ("pos-down" in cls) == (exp_bias < 0), cls)

        # --- cross-check one instrument-table cell: FII Index Futures Longs Δ on latest ---
        first_table = tables[0]
        fii_row = first_table.query_selector("tbody tr:nth-child(3)")
        cells = fii_row.query_selector_all("td")
        longs_delta = parse_num(cells[1].inner_text())
        exp_fii_long = row("31-07-2026","FII")["Future Index Long"] - row("30-07-2026","FII")["Future Index Long"]
        check("Index Futures FII Longs Δ matches", longs_delta == exp_fii_long, f"{longs_delta} vs {exp_fii_long}")

        # --- date nav re-renders ---
        first_net = first_table.query_selector("tbody tr:nth-child(3) td:nth-child(3)").inner_text()
        page.click("#d-prev")  # 30-07
        page.wait_for_timeout(200)
        tables2 = page.query_selector_all("#view-gross .main-col .instrument-block")
        prev_net = tables2[0].query_selector("tbody tr:nth-child(3) td:nth-child(3)").inner_text()
        spark_after = page.query_selector_all("#view-gross .spark-cell svg.sparkline")
        chip = page.query_selector("#d-picker").inner_text()
        check("date nav to prev updates chip", chip == "30-07-2026", chip)
        check("date nav re-renders values", prev_net != first_net, f"{prev_net} != {first_net}")
        check("sparklines re-rendered on nav", len(spark_after) == 24)
        page.click("#d-latest")
        page.wait_for_timeout(200)
        chip = page.query_selector("#d-picker").inner_text()
        check("Latest returns to latest date", chip == "31-07-2026", chip)
        tables3 = page.query_selector_all("#view-gross .main-col .instrument-block")
        back_net = tables3[0].query_selector("tbody tr:nth-child(3) td:nth-child(3)").inner_text()
        check("latest restores original value", back_net == first_net, f"{back_net} == {first_net}")

        # --- single nav: exactly one takeaways block ---
        tw_blocks = page.query_selector_all("#view-gross .takeaways")
        check("single nav: exactly one takeaways block", len(tw_blocks) == 1, f"got {len(tw_blocks)}")

        # --- rapid nav: no duplicate takeaways (stale-safe race fix) ---
        # already at latest here (previous section restored it)
        page.wait_for_timeout(50)
        for _ in range(6):
            page.click("#d-prev")   # rapid-fire, no waits
        page.wait_for_selector(".takeaway-item", timeout=10000)
        page.wait_for_timeout(500)  # let all in-flight callbacks settle
        tw_blocks = page.query_selector_all("#view-gross .takeaways")
        check("rapid nav: exactly one takeaways block", len(tw_blocks) == 1, f"got {len(tw_blocks)}")
        in_grid = page.query_selector("#view-gross .dash-grid .takeaways")
        check("rapid nav: takeaways inside current grid", in_grid is not None)
        tw_text = in_grid.inner_text() if in_grid else ""
        check("rapid nav: takeaways still show latest session", "31-07-2026" in tw_text, tw_text.splitlines()[0] if tw_text else "")
        # restore to latest for remaining checks
        page.click("#d-latest")
        page.wait_for_timeout(200)

        # --- deterministic race A/B: delay loadMoneyFlow in-page, rapid nav ---
        def patch_mf_delay(pg):
            # every render's loadMoneyFlow resolves 400ms later -> multiple
            # renders overlap in-flight callbacks deterministically.
            pg.evaluate("""() => {
              if (!window.__mfOrig) window.__mfOrig = NFOD.data.loadMoneyFlow.bind(NFOD.data);
              NFOD.data.loadMoneyFlow = () => new Promise(r => setTimeout(() => window.__mfOrig().then(r), 400));
            }""")

        def rapid_nav_count(pg):
            pg.goto(URL, wait_until="networkidle", timeout=30000)
            pg.wait_for_selector(".takeaway-item", timeout=15000)
            pg.wait_for_timeout(100)
            patch_mf_delay(pg)
            pg.click("#d-latest")
            pg.wait_for_timeout(50)
            for _ in range(6):
                pg.click("#d-prev")
            pg.wait_for_timeout(1500)  # let all delayed callbacks settle
            return len(pg.query_selector_all("#view-gross .takeaways"))

        n_fixed = rapid_nav_count(page)
        check("race A/B (delayed, fixed code): exactly one block", n_fixed == 1, f"got {n_fixed}")

        old_js = subprocess.check_output(["git", "show", "HEAD:views/gross.js"], text=True)
        ctx2 = browser.new_context(accept_downloads=True)
        page2 = ctx2.new_page()
        page2.route("**/views/gross.js", lambda route: route.fulfill(body=old_js, content_type="application/javascript"))
        n_old = rapid_nav_count(page2)
        check("race A/B (delayed, pre-fix code): duplicates reproduce", n_old >= 2, f"got {n_old}")
        ctx2.close()

        # --- export CSV downloads ---
        with page.expect_download(timeout=10000) as dl_info:
            page.query_selector(".export-csv[data-inst='index-futures']").click()
        dl = dl_info.value
        check("Export CSV downloads file", dl.suggested_filename.startswith("index-futures-") and dl.suggested_filename.endswith(".csv"), dl.suggested_filename)
        path = dl.path()
        content = open(path, encoding="utf-8").read()
        check("CSV content has 5 rows", len(content.strip().splitlines()) == 5, str(len(content.strip().splitlines())))

        # --- console errors (exclude expected 404s) ---
        ok404 = [u for u in failed_reqs if "verdict.js" in u or "charts.js" in u]
        other_failed = [u for u in failed_reqs if not ("verdict.js" in u or "charts.js" in u)]
        page_errs_filtered = [e for e in page_errs]
        # network 404s don't surface as page errors; filter console errors mentioning failed net req
        console_filtered = [e for e in console_errs if not ("verdict.js" in e or "charts.js" in e or "Failed to load" in e or "net::ERR" in e)]
        check("only expected 404s (verdict/charts)", len(other_failed) == 0 and len(ok404) >= 2, f"other_failed={other_failed} ok404={len(ok404)}")
        check("no page errors", len(page_errs_filtered) == 0, str(page_errs_filtered))
        check("no console errors", len(console_filtered) == 0, str(console_filtered))

        browser.close()

    fails = [r for r in results if not r[1]]
    print("\n" + ("ALL CHECKS PASSED" if not fails else f"{len(fails)} FAILURES"))
    sys.exit(1 if fails else 0)

if __name__ == "__main__":
    main()
