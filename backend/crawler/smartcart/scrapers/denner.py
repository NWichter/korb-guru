"""
Denner - Prospekt Scraper
Tier 2: Issuu Wochenprospekt (Docling OCR) + SSR HTML offers from aktionen page
"""
import re
import tempfile

from bs4 import BeautifulSoup

from crawler.smartcart.scrapers.base import BaseScraper
from crawler.smartcart.models.product import ScrapedProduct, ScrapedProspekt
from crawler.smartcart.utils.dates import get_current_kw, format_kw
from crawler.smartcart.utils.http import fetch_text, fetch_bytes, head_check

# Issuu page image URL pattern
ISSUU_IMAGE_URL = "https://image.isu.pub/{username}/{slug}/jpg/page_{page}.jpg"
ISSUU_MAX_PAGES = 16


def _parse_price(text: str) -> float | None:
    """Extract price from text like 'CHF 2.95' or '2,95'."""
    match = re.search(r"(\d+[.,]\d{2})", text.replace("CHF", "").strip())
    if match:
        return float(match.group(1).replace(",", "."))
    return None


class DennerScraper(BaseScraper):
    chain = "denner"

    def _build_issuu_url(self, year: int, kw: int) -> str:
        return f"https://issuu.com/denner-ch/docs/{year}-{format_kw(kw)}-de"

    def _build_issuu_slug(self, year: int, kw: int) -> str:
        return f"{year}-{format_kw(kw)}-de"

    async def _scrape_issuu_pages(
        self, year: int, kw: int, valid_from: str | None = None, valid_to: str | None = None
    ) -> list[ScrapedProduct]:
        """Download Issuu page images and extract products via Docling."""
        slug = self._build_issuu_slug(year, kw)
        username = "denner-ch"

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
                    tmp.name, "denner", valid_from, valid_to
                )
                products.extend(page_products)
                self.logger.info(f"  Page {page_num}: {len(page_products)} products")

        self.logger.info(f"Issuu total: {len(products)} products")
        return products

    async def scrape(self) -> ScrapedProspekt:
        kw_info = get_current_kw()
        kw = kw_info["kw_str"]
        self.logger.info(f"Scraping KW{kw} {kw_info['year']}...")

        issuu_url = self._build_issuu_url(kw_info["year"], kw_info["week"])
        og_title = ""
        og_desc = ""

        try:
            html = await fetch_text(issuu_url)
            soup = BeautifulSoup(html, "html.parser")
            og_title = (soup.find("meta", property="og:title") or {}).get("content", "")
            og_desc = (soup.find("meta", property="og:description") or {}).get("content", "")
        except Exception as e:
            self.logger.warning(f"Issuu not available: {e}")

        # 1. Scrape SSR HTML offers
        products = []
        seen_names: set[str] = set()
        try:
            html = await fetch_text("https://www.denner.ch/de/aktionen-und-sortiment/aktuelle-aktionen")
            soup = BeautifulSoup(html, "html.parser")

            main = soup.find("main") or soup
            for el in main.select("[class*='product-card'], [class*='product-tile'], [class*='promotion-item']"):
                name_el = el.select_one("[class*='product-name'], [class*='product-title'], h3, h4")
                price_el = el.select_one("[class*='price']")
                img_el = el.select_one("img[src*='product'], img[src*='denner'], img[data-src]")

                name = name_el.get_text(strip=True) if name_el else ""
                if not name or len(name) < 3:
                    continue
                name_lower = name.lower()
                if name_lower in seen_names:
                    continue
                seen_names.add(name_lower)

                price = _parse_price(price_el.get_text(strip=True)) if price_el else None
                img_url = None
                if img_el:
                    img_url = img_el.get("src") or img_el.get("data-src")

                products.append(ScrapedProduct(
                    retailer="denner",
                    name=name,
                    price=price,
                    image_url=img_url,
                ))
        except Exception as e:
            self.logger.warning(f"HTML scrape failed: {e}")

        self.logger.info(f"Found {len(products)} offers from HTML")

        # 2. Extract products from Issuu page images via Docling
        issuu_products = await self._scrape_issuu_pages(
            kw_info["year"], kw_info["week"],
            valid_from=kw_info["monday"], valid_to=kw_info["saturday"],
        )

        # Merge, deduplicating against HTML products
        for p in issuu_products:
            if p.name.lower() not in seen_names:
                products.append(p)
                seen_names.add(p.name.lower())

        self.logger.info(f"Total: {len(products)} products (HTML + Issuu)")

        return ScrapedProspekt(
            chain="Denner",
            type="wochenprospekt",
            kw=f"KW{kw}",
            year=kw_info["year"],
            valid_from=kw_info["monday"],
            valid_to=kw_info["saturday"],
            url=issuu_url,
            title=og_title,
            description=og_desc,
            products=products,
        )
