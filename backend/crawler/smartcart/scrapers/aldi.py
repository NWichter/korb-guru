"""
Aldi Suisse - Prospekt Scraper
Tier 1: Direct PDF download from Scene7 CDN + pdfplumber extraction
"""
from crawler.smartcart.config import PROSPEKTE_DIR
from crawler.smartcart.scrapers.base import BaseScraper
from crawler.smartcart.models.product import ScrapedProspekt
from crawler.smartcart.utils.dates import get_current_kw
from crawler.smartcart.utils.http import head_check, fetch_bytes
from crawler.smartcart.utils.pdf import extract_products_from_pdf


class AldiScraper(BaseScraper):
    chain = "aldi"

    def _build_url(self, kw: int) -> str:
        return f"https://s7g10.scene7.com/is/content/aldi/AW_KW{kw}_Sp01_DE_FINAL"

    async def scrape(self) -> ScrapedProspekt:
        kw_info = get_current_kw()
        self.logger.info(f"Scraping KW{kw_info['kw_str']}...")

        url = self._build_url(kw_info["week"])
        exists = await head_check(url)
        products = []

        if exists:
            PROSPEKTE_DIR.mkdir(parents=True, exist_ok=True)
            filename = f"aldi_wochenflyer_{kw_info['monday']}_{kw_info['saturday']}.pdf"
            filepath = PROSPEKTE_DIR / filename
            if not filepath.exists():
                data = await fetch_bytes(url)
                filepath.write_bytes(data)
                self.logger.info(f"Downloaded: {filename}")
            else:
                self.logger.info(f"Already exists: {filename}")

            products = extract_products_from_pdf(
                filepath, "aldi",
                valid_from=kw_info["monday"],
                valid_to=kw_info["saturday"],
            )
        else:
            self.logger.warning(f"No PDF found for KW{kw_info['week']}")

        return ScrapedProspekt(
            chain="Aldi Suisse",
            type="wochenflyer",
            kw=f"KW{kw_info['kw_str']}",
            year=kw_info["year"],
            valid_from=kw_info["monday"],
            valid_to=kw_info["saturday"],
            url=url if exists else None,
            products=products,
        )
