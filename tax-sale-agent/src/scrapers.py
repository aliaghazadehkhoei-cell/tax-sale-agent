import json, asyncio
import pandas as pd
from pathlib import Path
from playwright.async_api import async_playwright

class ClerkScraper:
    def __init__(self, headless: bool = True):
        self.headless = headless

    async def search(self, query: str, max_pages: int = 3) -> pd.DataFrame:
        recs = []
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=self.headless)
            page = await browser.new_page()
            url = "https://www.cclerk.hctx.net/applications/websearch/RPsearch.aspx"
            await page.goto(url, timeout=60000)
            # Try common inputs; page may change structure
            for sel in ["input#SearchText","input[name='txtSearch']","input[name='OwnerName']","input[name='PropertyAddress']"]:
                if await page.query_selector(sel):
                    await page.fill(sel, query)
                    break
            for btn in ["input#btnSearch","button:has-text('Search')","input[type='submit']"]:
                if await page.query_selector(btn):
                    await page.click(btn); break
            # Paginate
            for _ in range(max_pages):
                await page.wait_for_selector("table", timeout=20000)
                rows = await page.query_selector_all("table tr")
                for r in rows[1:]:
                    tds = await r.query_selector_all("td")
                    cols = [await td.inner_text() for td in tds]
                    if not cols: continue
                    recs.append({
                        "Grantor": cols[0] if len(cols)>0 else "",
                        "Grantee": cols[1] if len(cols)>1 else "",
                        "DocType": cols[2] if len(cols)>2 else "",
                        "InstrumentNo": cols[3] if len(cols)>3 else "",
                        "RecordedDate": cols[4] if len(cols)>4 else "",
                        "Legal": cols[5] if len(cols)>5 else "",
                        "Notes": cols[6] if len(cols)>6 else ""
                    })
                nxt = await page.query_selector("a[title='Next'], a:has-text('Next')")
                if not nxt: break
                await nxt.click()
            await browser.close()
        return pd.DataFrame(recs).drop_duplicates()

class MunicipalScraper:
    def __init__(self, config_path: str, headless: bool = True):
        self.headless = headless
        self.cfg = json.loads(Path(config_path).read_text())

    async def scrape(self, max_pages: int = 5) -> pd.DataFrame:
        recs = []
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=self.headless)
            page = await browser.new_page()
            await page.goto(self.cfg["start_url"], timeout=60000)
            for _ in range(max_pages):
                await page.wait_for_selector(self.cfg["row_selector"], timeout=30000)
                rows = await page.query_selector_all(self.cfg["row_selector"])
                for r in rows:
                    rec = {}
                    for field, sel in self.cfg["fields"].items():
                        el = await r.query_selector(sel)
                        rec[field] = (await el.inner_text()) if el else ""
                    recs.append(rec)
                next_sel = self.cfg.get("next_selector")
                if not next_sel: break
                nxt = await page.query_selector(next_sel)
                if not nxt: break
                await nxt.click()
            await browser.close()
        return pd.DataFrame(recs).drop_duplicates()
