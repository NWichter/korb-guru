"""
Coop - Prospekt & Aktionen Scraper
Tier 3 (Playwright): PDF download from ePaper + aktionen page scraping
"""
import re

from crawler.smartcart.config import PROSPEKTE_DIR
from crawler.smartcart.scrapers.base import BaseScraper
from crawler.smartcart.models.product import ScrapedProduct, ScrapedProspekt
from crawler.smartcart.utils.dates import get_current_kw
from crawler.smartcart.utils.pdf import extract_products_from_pdf


STOREFRONT_ZH = 1132


class CoopScraper(BaseScraper):
    chain = "coop"

    async def _scrape_aktionen(self) -> list[ScrapedProduct]:
        """Scrape current offers from Coop aktionen page via Playwright."""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return []

        products = []
        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True)
                try:
                    page = await browser.new_page()
                    await page.goto(
                        "https://www.coop.ch/de/aktionen.html",
                        wait_until="networkidle",
                        timeout=30000,
                    )
                    await page.wait_for_timeout(3000)

                    items = await page.evaluate("""() => {
                        const results = [];
                        const cards = document.querySelectorAll(
                            '[class*="product"], [class*="Product"], [class*="offer"], article'
                        );
                        cards.forEach(card => {
                            // Skip nav/footer elements
                            if (card.closest('nav, footer, header')) return;
                            const nameEl = card.querySelector(
                                '[class*="product-name"], [class*="productName"], h3, h4, [class*="title"]'
                            );
                            const priceEl = card.querySelector(
                                '[class*="price"], [class*="Price"]'
                            );
                            const imgEl = card.querySelector('img');
                            const name = nameEl?.textContent?.trim();
                            const priceText = priceEl?.textContent?.trim();
                            const img = imgEl?.src || imgEl?.getAttribute('data-src');
                            if (name && name.length > 2) {
                                results.push({name, price: priceText || '', img: img || ''});
                            }
                        });
                        return results;
                    }""")

                    seen: set[str] = set()
                    for item in items:
                        name = item["name"]
                        if name.lower() in seen:
                            continue
                        seen.add(name.lower())

                        price = None
                        price_match = re.search(r"(\d+[.,]\d{2})", item.get("price", ""))
                        if price_match:
                            price = float(price_match.group(1).replace(",", "."))

                        products.append(ScrapedProduct(
                            retailer="coop",
                            name=name,
                            price=price,
                            image_url=item.get("img") or None,
                        ))
                finally:
                    await browser.close()
        except Exception as e:
            self.logger.warning(f"Aktionen scrape failed: {e}")

        return products

    async def scrape(self) -> ScrapedProspekt:
        kw_info = get_current_kw()
        kw = kw_info["kw_str"]
        self.logger.info(f"Scraping KW{kw} {kw_info['year']} (Storefront {STOREFRONT_ZH})...")

        try:
            from playwright.async_api import async_playwright
        except ImportError:
            self.logger.warning("Playwright not installed")
            return ScrapedProspekt(
                chain="Coop", type="coopzeitung", kw=f"KW{kw}", year=kw_info["year"],
                valid_from=kw_info["monday"], valid_to=kw_info["saturday"],
                url=f"https://epaper.coopzeitung.ch/storefront/{STOREFRONT_ZH}",
            )

        PROSPEKTE_DIR.mkdir(parents=True, exist_ok=True)
        pdf_filename = f"coop_zeitung-zh_{kw_info['monday']}_{kw_info['saturday']}.pdf"
        pdf_path = PROSPEKTE_DIR / pdf_filename
        pdf_products = []

        if pdf_path.exists():
            self.logger.info(f"Already exists: {pdf_filename}")
        else:
            # Try downloading PDF via ePaper
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True)
                try:
                    page = await browser.new_page()
                    await page.goto(
                        f"https://epaper.coopzeitung.ch/storefront/{STOREFRONT_ZH}",
                        wait_until="networkidle",
                        timeout=30000,
                    )
                    await page.wait_for_timeout(3000)

                    download_btn = await page.query_selector(
                        '[class*="download"], a:has-text("herunterladen"), button:has-text("Download")'
                    )
                    if download_btn:
                        try:
                            async with page.expect_download(timeout=10000) as download_info:
                                await download_btn.click()
                            download = await download_info.value
                            await download.save_as(str(pdf_path))
                            self.logger.info(f"Downloaded: {pdf_filename}")
                        except Exception as e:
                            self.logger.warning(f"Download button failed: {e}")
                finally:
                    await browser.close()

        # Extract products from PDF if available
        if pdf_path.exists():
            pdf_products = extract_products_from_pdf(
                pdf_path, "coop",
                valid_from=kw_info["monday"],
                valid_to=kw_info["saturday"],
            )

        # Also scrape aktionen HTML page for more products
        aktionen_products = await self._scrape_aktionen()
        self.logger.info(f"Found {len(pdf_products)} from PDF, {len(aktionen_products)} from aktionen page")

        # Merge, preferring aktionen (more structured data)
        all_products = aktionen_products + pdf_products

        return ScrapedProspekt(
            chain="Coop", type="coopzeitung", kw=f"KW{kw}", year=kw_info["year"],
            valid_from=kw_info["monday"], valid_to=kw_info["saturday"],
            url=f"https://epaper.coopzeitung.ch/storefront/{STOREFRONT_ZH}",
            products=all_products,
        )
