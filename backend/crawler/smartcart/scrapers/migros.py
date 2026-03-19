"""
Migros - Prospekt & Aktionen Scraper
Tier 2: Issuu Wochenflyer (Docling OCR) + Playwright HTML scraping of aktionen page
"""
import tempfile

from bs4 import BeautifulSoup

from crawler.smartcart.scrapers.base import BaseScraper
from crawler.smartcart.models.product import ScrapedProduct, ScrapedProspekt
from crawler.smartcart.utils.dates import get_current_kw, format_kw
from crawler.smartcart.utils.http import fetch_text, fetch_bytes, head_check

# Issuu page image URL pattern
ISSUU_IMAGE_URL = "https://image.isu.pub/{username}/{slug}/jpg/page_{page}.jpg"
ISSUU_MAX_PAGES = 16


class MigrosScraper(BaseScraper):
    chain = "migros"

    def _build_issuu_url(self, year: int, kw: int) -> str:
        return f"https://issuu.com/m-magazin/docs/migros-wochenflyer-{format_kw(kw)}-{year}-d-zh"

    def _build_issuu_slug(self, year: int, kw: int) -> str:
        return f"migros-wochenflyer-{format_kw(kw)}-{year}-d-aa"

    async def _scrape_issuu_pages(
        self, year: int, kw: int, valid_from: str | None = None, valid_to: str | None = None
    ) -> list[ScrapedProduct]:
        """Download Issuu page images and extract products via Docling."""
        slug = self._build_issuu_slug(year, kw)
        username = "m-magazin"

        pub_url = f"https://issuu.com/{username}/docs/{slug}"
        if not await head_check(pub_url):
            self.logger.warning(f"Issuu publication not found: {slug}")
            return []

        self.logger.info(f"Downloading Issuu pages: {username}/{slug}")

        from crawler.smartcart.utils.pdf import extract_products_from_pdf

        products = []
        for page_num in range(1, ISSUU_MAX_PAGES + 1):
            img_url = ISSUU_IMAGE_URL.format(
                username=username, slug=slug, page=page_num
            )
            try:
                img_bytes = await fetch_bytes(img_url)
            except Exception:
                self.logger.info(f"  Page {page_num}: end of publication")
                break

            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                tmp.write(img_bytes)
                tmp.flush()
                page_products = extract_products_from_pdf(
                    tmp.name, "migros", valid_from, valid_to
                )
                products.extend(page_products)
                self.logger.info(f"  Page {page_num}: {len(page_products)} products")

        self.logger.info(f"Issuu total: {len(products)} products")
        return products

    async def _scrape_aktionen(self) -> list[ScrapedProduct]:
        """Scrape current offers from Migros aktionen page via Playwright."""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            self.logger.warning("Playwright not installed, skipping aktionen scrape")
            return []

        products = []
        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True)
                try:
                    page = await browser.new_page()
                    await page.goto(
                        "https://www.migros.ch/de/aktionen.html",
                        wait_until="networkidle",
                        timeout=30000,
                    )
                    await page.wait_for_timeout(3000)

                    items = await page.evaluate("""() => {
                        const results = [];
                        const cards = document.querySelectorAll(
                            '[class*="product-card"], [class*="ProductCard"], [class*="offer-card"], article[class*="product"]'
                        );
                        cards.forEach(card => {
                            const nameEl = card.querySelector(
                                '[class*="product-name"], [class*="ProductName"], h2, h3, [class*="title"]'
                            );
                            const priceEl = card.querySelector(
                                '[class*="price"], [class*="Price"]'
                            );
                            const imgEl = card.querySelector('img');
                            const discountEl = card.querySelector(
                                '[class*="discount"], [class*="Discount"], [class*="badge"]'
                            );
                            const name = nameEl?.textContent?.trim();
                            const priceText = priceEl?.textContent?.trim();
                            const img = imgEl?.src || imgEl?.getAttribute('data-src');
                            const discountText = discountEl?.textContent?.trim();
                            if (name && name.length > 2) {
                                results.push({name, price: priceText || '', img: img || '', discount: discountText || ''});
                            }
                        });
                        return results;
                    }""")

                    import re
                    for item in items:
                        price = None
                        price_match = re.search(r"(\d+[.,]\d{2})", item.get("price", ""))
                        if price_match:
                            price = float(price_match.group(1).replace(",", "."))

                        discount = None
                        discount_match = re.search(r"(\d{1,2})\s*%", item.get("discount", ""))
                        if discount_match:
                            discount = float(discount_match.group(1))

                        products.append(ScrapedProduct(
                            retailer="migros",
                            name=item["name"],
                            price=price,
                            discount_pct=discount,
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
        self.logger.info(f"Scraping KW{kw} {kw_info['year']} (Region ZH)...")

        issuu_url = self._build_issuu_url(kw_info["year"], kw_info["week"])
        og_title = ""
        og_desc = ""

        try:
            html = await fetch_text(issuu_url)
            soup = BeautifulSoup(html, "html.parser")
            og_title = (soup.find("meta", property="og:title") or {}).get("content", "")
            og_desc = (soup.find("meta", property="og:description") or {}).get("content", "")
        except Exception as e:
            self.logger.warning(f"Issuu page not available: {e}")

        # 1. Extract products from Issuu page images via Docling
        issuu_products = await self._scrape_issuu_pages(
            kw_info["year"], kw_info["week"],
            valid_from=kw_info["monday"], valid_to=kw_info["saturday"],
        )

        # 2. Scrape HTML aktionen page via Playwright
        html_products = await self._scrape_aktionen()
        self.logger.info(f"Found {len(html_products)} products from aktionen page")

        # Merge: HTML products first, then Issuu products (deduplicated)
        products = list(html_products)
        existing_names = {p.name.lower() for p in products}
        for p in issuu_products:
            if p.name.lower() not in existing_names:
                products.append(p)
                existing_names.add(p.name.lower())

        self.logger.info(f"Total: {len(products)} products (HTML + Issuu)")

        return ScrapedProspekt(
            chain="Migros",
            type="wochenflyer",
            region="ZH",
            kw=f"KW{kw}",
            year=kw_info["year"],
            valid_from=kw_info["monday"],
            valid_to=kw_info["saturday"],
            url=issuu_url,
            title=og_title,
            description=og_desc,
            products=products,
        )
