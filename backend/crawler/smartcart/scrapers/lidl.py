"""
Lidl Switzerland - Prospekt Scraper
Tier 4: Playwright (JS-rendered PDF page) + pdfplumber extraction
"""
from crawler.smartcart.config import PROSPEKTE_DIR
from crawler.smartcart.scrapers.base import BaseScraper
from crawler.smartcart.models.product import ScrapedProspekt
from crawler.smartcart.utils.dates import get_current_kw
from crawler.smartcart.utils.pdf import extract_products_from_pdf


class LidlScraper(BaseScraper):
    chain = "lidl"

    async def scrape(self) -> ScrapedProspekt:
        kw_info = get_current_kw()
        kw = kw_info["kw_str"]
        self.logger.info(f"Scraping KW{kw} {kw_info['year']}...")

        try:
            from playwright.async_api import async_playwright
        except ImportError:
            self.logger.error("Playwright not installed.")
            return ScrapedProspekt(
                chain="Lidl", type="prospekt", kw=f"KW{kw}", year=kw_info["year"],
                valid_from=kw_info["monday"], valid_to=kw_info["saturday"],
                url="https://www.lidl.ch/c/de-CH/werbeprospekte-als-pdf/s10019683",
            )

        PROSPEKTE_DIR.mkdir(parents=True, exist_ok=True)
        downloaded_files = []

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                pdf_urls: list[str] = []

                page.on("response", lambda resp: (
                    pdf_urls.append(resp.url)
                    if "pdf" in (resp.headers.get("content-type", "")) or resp.url.endswith(".pdf")
                    else None
                ))

                await page.goto(
                    "https://www.lidl.ch/c/de-CH/werbeprospekte-als-pdf/s10019683",
                    wait_until="networkidle",
                    timeout=30000,
                )
                await page.wait_for_timeout(3000)

                links = await page.evaluate("""() => {
                    const results = [];
                    document.querySelectorAll('a[href*=".pdf"]').forEach(a => {
                        results.push({href: a.href, text: a.textContent.trim()});
                    });
                    document.querySelectorAll('[data-href*=".pdf"], [download]').forEach(el => {
                        const href = el.getAttribute('data-href') || el.getAttribute('href');
                        if (href) results.push({href, text: el.textContent.trim()});
                    });
                    return results;
                }""")

                all_urls = list(set(pdf_urls + [l["href"] for l in links if l.get("href")]))

                if all_urls:
                    from crawler.smartcart.utils.http import fetch_bytes
                    for url in all_urls:
                        try:
                            label = "wochenflyer" if "Woche" in url else "prospekt"
                            filename = f"lidl_{label}_{kw_info['monday']}_{kw_info['saturday']}.pdf"
                            filepath = PROSPEKTE_DIR / filename
                            if not filepath.exists():
                                data = await fetch_bytes(url)
                                filepath.write_bytes(data)
                                self.logger.info(f"Downloaded: {filename}")
                            else:
                                self.logger.info(f"Already exists: {filename}")
                            downloaded_files.append(str(filepath))
                        except Exception as e:
                            self.logger.error(f"Download failed: {e}")
                else:
                    self.logger.warning("No PDF URLs found on page")
            finally:
                await browser.close()

        # Extract products from all downloaded PDFs
        all_products = []
        for pdf_file in downloaded_files:
            products = extract_products_from_pdf(
                pdf_file, "lidl",
                valid_from=kw_info["monday"],
                valid_to=kw_info["saturday"],
            )
            all_products.extend(products)

        return ScrapedProspekt(
            chain="Lidl", type="prospekt", kw=f"KW{kw}", year=kw_info["year"],
            valid_from=kw_info["monday"], valid_to=kw_info["saturday"],
            url="https://www.lidl.ch/c/de-CH/werbeprospekte-als-pdf/s10019683",
            products=all_products,
        )
