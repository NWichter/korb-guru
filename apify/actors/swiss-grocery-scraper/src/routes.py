"""
Request handlers for each Swiss retailer.

Scraping strategies — PDF-first approach (verified March 2026):
- Aldi:   PDF download from Scene7 CDN → Docling OCR
- Lidl:   Leaflets API pdfUrl → Docling OCR (fallback: API product links)
- Coop:   ePaper PDF download → Docling OCR (fallback: Playwright HTML)
- Denner: BeautifulSoup on SSR HTML (.product-item selectors)
- Migros: Playwright on /de/offers/home (article[mo-basic-product-card])

Denner & Migros have no accessible PDF source (Issuu blocked from datacenter IPs).
"""

import logging
import re
from datetime import date, timedelta

import httpx

from src.pdf_extract import extract_products_from_pdf_bytes

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "de-CH,de;q=0.9",
}

PRICE_RE = re.compile(r"(\d+[.,]\d{2})")
PRICE_MIN = 0.10
PRICE_MAX = 500.0

# Non-grocery keywords to filter out from product names (beauty, electronics, etc.)
_NON_GROCERY_KEYWORDS = re.compile(
    r"\b(?:cien|beauty|kosmetik|pinsel|manik[uü]re|pedik[uü]re|multigroomer|"
    r"personenwaage|schmucktablett|barttrimmer|b[uü]rste|"
    r"velosattel|velozubeh[oö]r|kulturtopf|"
    r"laptop|tablet|smartphone|kopfh[oö]rer|bluetooth|"
    r"bettwäsche|duvet|kissen|gardine|vorhang)\b",
    re.IGNORECASE,
)


def _parse_price(text: str) -> float | None:
    """Extract and validate price from text."""
    match = PRICE_RE.search(text.replace("CHF", "").replace("Fr.", "").strip())
    if match:
        price = float(match.group(1).replace(",", "."))
        if PRICE_MIN <= price <= PRICE_MAX:
            return price
    return None


def _parse_discount(text: str) -> float | None:
    """Extract discount percentage from text like '38%', '½ PREIS', '50% ab 2'."""
    if not text:
        return None
    if "½" in text or "1/2" in text:
        return 50.0
    m = re.search(r"(\d{1,2})\s*%", text)
    return float(m.group(1)) if m else None


# ---------------------------------------------------------------------------
# Aldi — PDF download + Docling extraction
# ---------------------------------------------------------------------------
async def scrape_aldi(max_items: int = 200, region: str = "zurich") -> list[dict]:
    """Download Aldi weekly PDF flyer and extract products with Docling."""
    today = date.today()
    kw = today.isocalendar()[1]

    # Aldi Suisse uses multiple URL patterns for weekly flyers
    pdf_urls = [
        f"https://s7g10.scene7.com/is/content/aldi/AW_KW{kw}_Sp01_DE_FINAL",
        f"https://s7g10.scene7.com/is/content/aldi/AW_KW{kw:02d}_Sp01_DE_FINAL",
        f"https://s7g10.scene7.com/is/content/aldi/AW_KW{kw}_DE",
    ]

    async with httpx.AsyncClient(headers=HEADERS, timeout=60.0) as client:
        for pdf_url in pdf_urls:
            try:
                resp = await client.get(pdf_url)
                if resp.is_success and len(resp.content) > 1000:
                    products = await extract_products_from_pdf_bytes(
                        resp.content, "aldi"
                    )
                    logger.info(
                        f"Aldi: {len(products)} products from KW{kw} PDF ({pdf_url})"
                    )
                    return products[:max_items]
            except Exception as e:
                logger.warning(f"Aldi PDF attempt failed ({pdf_url}): {e}")

    logger.warning(f"No Aldi PDF found for KW{kw}")
    return []


# ---------------------------------------------------------------------------
# Migros — Playwright scraping of offers page
# ---------------------------------------------------------------------------
async def scrape_migros(max_items: int = 200, region: str = "zurich") -> list[dict]:
    """Scrape Migros offers via Playwright on /de/offers/home.

    Migros is an Angular SPA that loads product data via authenticated API.
    We use Playwright to render the page and extract from the DOM.
    Selectors: article[mo-basic-product-card], mo-product-name, mo-product-price.
    """
    try:
        from crawlee.crawlers import PlaywrightCrawler, PlaywrightCrawlingContext

        found_products: list[dict] = []

        crawler = PlaywrightCrawler(
            max_requests_per_crawl=1,
            headless=True,
            request_handler_timeout=timedelta(seconds=90),
        )

        @crawler.router.default_handler
        async def migros_handler(context: PlaywrightCrawlingContext) -> None:
            context.log.info(f"Scraping Migros offers: {context.request.url}")
            # Wait for product cards to render (Angular SPA)
            await context.page.wait_for_timeout(5000)

            # Scroll to trigger lazy loading
            for _ in range(3):
                await context.page.evaluate("window.scrollBy(0, 1000)")
                await context.page.wait_for_timeout(1500)

            items = await context.page.evaluate("""() => {
                const results = [];
                const cards = document.querySelectorAll(
                    'article[mo-basic-product-card]'
                );
                cards.forEach(card => {
                    // Name: mo-product-name > .name + .desc
                    const brand = card.querySelector('mo-product-name .name')
                        ?.textContent?.trim() || '';
                    const desc = card.querySelector(
                        'mo-product-name .desc span[data-testid]'
                    )?.textContent?.trim() || '';
                    const name = (brand ? brand + ' ' : '') + desc;

                    // Price
                    const currentPrice = card.querySelector(
                        '[data-testid="current-price"]'
                    )?.textContent?.trim() || '';
                    const originalPrice = card.querySelector(
                        '[data-testid="original-price"]'
                    )?.textContent?.trim() || '';

                    // Discount badge
                    const badge = card.querySelector(
                        'span[data-cy*="PERCENTAGE"] span[data-testid="description"]'
                    )?.textContent?.trim() || '';

                    // Image
                    const img = card.querySelector(
                        'mo-product-image-universal img'
                    )?.src || '';

                    if (name && name.length > 2) {
                        results.push({
                            name, price: currentPrice,
                            originalPrice, discount: badge, img
                        });
                    }
                });
                return results;
            }""")

            context.log.info(f"Found {len(items)} Migros products")

            seen: set[str] = set()
            for item in items:
                name = item["name"]
                if name.lower() in seen:
                    continue
                seen.add(name.lower())

                found_products.append(
                    {
                        "retailer": "migros",
                        "name": name,
                        "price": _parse_price(item.get("price", "")),
                        "discount_pct": _parse_discount(item.get("discount", "")),
                        "image_url": item.get("img") or None,
                        "category": "offer",
                        "region": region,
                    }
                )

        await crawler.run(["https://www.migros.ch/de/offers/home"])
        logger.info(f"Migros: {len(found_products)} products")
        return found_products[:max_items]

    except Exception as e:
        logger.error(f"Migros scraping failed: {e}")
        return []


# ---------------------------------------------------------------------------
# Coop — ePaper JSON API → page PDFs → pdfplumber extraction
# ---------------------------------------------------------------------------
_EPAPER_BASE = "https://epaper.coopzeitung.ch/epaper/1.0"
_COOP_DEF_ID = 1130  # Coopzeitung German edition

# Department containing product advertisements / offer pages
_OFFER_DEPARTMENTS = {"anzeigen"}


async def scrape_coop(max_items: int = 200, region: str = "zurich") -> list[dict]:
    """Scrape Coop via ePaper JSON API (no browser needed).

    The Coopzeitung ePaper (epaper.coopzeitung.ch) exposes a public JSON API.
    Strategy:
    1. Find latest edition via findEditionsFromDate
    2. Get all pages via getPages
    3. Filter to "Anzeigen" department (product advertisements)
    4. Download page PDFs from pre-signed S3 URLs
    5. Extract products with pdfplumber
    """
    today = date.today()
    products: list[dict] = []

    async with httpx.AsyncClient(headers=HEADERS, timeout=60.0) as client:
        # Step 1: Find latest edition
        find_resp = await client.post(
            f"{_EPAPER_BASE}/findEditionsFromDate",
            json={
                "editions": [
                    {"publicationDate": today.isoformat(), "defId": _COOP_DEF_ID}
                ],
                "startDate": (today - timedelta(days=14)).isoformat(),
                "maxHits": 3,
            },
        )
        if not find_resp.is_success:
            logger.warning(f"Coop ePaper findEditions: HTTP {find_resp.status_code}")
            return []

        resp_json = find_resp.json()
        edition_list = resp_json.get("data", [])
        if not edition_list:
            logger.warning("Coop: no editions found")
            return []

        # Each edition entry has { pages: [{...metadata}], inlays: [] }
        first_edition = edition_list[0]
        pub_date = first_edition["pages"][0].get(
            "publicationDate", today.isoformat()
        )
        logger.info(f"Coop: latest edition {pub_date}")

        # Step 2: Get all pages for this edition
        pages_resp = await client.post(
            f"{_EPAPER_BASE}/getPages",
            json={
                "editions": [{"defId": _COOP_DEF_ID, "publicationDate": pub_date}]
            },
        )
        if not pages_resp.is_success:
            logger.warning(f"Coop ePaper getPages: HTTP {pages_resp.status_code}")
            return []

        pages_json = pages_resp.json()
        all_pages = pages_json.get("data", {}).get("pages", [])
        if not all_pages:
            logger.warning("Coop: no pages returned")
            return []

        # Step 3: Filter to offer-related departments
        offer_pages = [
            pg for pg in all_pages
            if (pg.get("pmDepartment") or "").lower() in _OFFER_DEPARTMENTS
        ]

        if not offer_pages:
            logger.info("Coop: no department match, using first 20 pages")
            offer_pages = all_pages[:20]
        else:
            logger.info(
                f"Coop: {len(offer_pages)} pages from offer departments "
                f"(out of {len(all_pages)} total)"
            )

        # Step 4: Download page PDFs and extract products
        # Limit to 30 pages max to keep runtime reasonable
        seen: set[str] = set()
        for pg in offer_pages[:30]:
            doc_urls = pg.get("pageDocUrl", {})
            highres = doc_urls.get("HIGHRES", {})
            pdf_url = highres.get("url")

            if not pdf_url:
                continue

            try:
                pdf_resp = await client.get(pdf_url)
                if not pdf_resp.is_success or len(pdf_resp.content) < 500:
                    continue

                page_num = pg.get("pmPageNumber", 0)
                # skip_ocr=True: single-page PDFs with 1-4 products
                # are normal for ePaper pages — don't trigger slow Docling
                page_products = await extract_products_from_pdf_bytes(
                    pdf_resp.content, "coop", f"coop-page-{page_num}.pdf",
                    skip_ocr=True,
                )

                for p in page_products:
                    name_lower = p["name"].lower()
                    if name_lower not in seen:
                        seen.add(name_lower)
                        p["region"] = region
                        products.append(p)

            except Exception as e:
                logger.warning(
                    f"Coop page {pg.get('pmPageNumber', '?')} PDF failed: {e}"
                )

    logger.info(f"Coop: {len(products)} products from ePaper")
    return products[:max_items]


# ---------------------------------------------------------------------------
# Denner — BeautifulSoup HTML scraping (SSR / Nuxt)
# ---------------------------------------------------------------------------
async def scrape_denner(max_items: int = 200, region: str = "zurich") -> list[dict]:
    """Scrape Denner aktionen page via BeautifulSoup.

    Denner uses Nuxt 3 with SSR — product data is in the initial HTML.
    Selectors: .product-item, .product-item__title, .price-tag__price,
    .price-tag__discount, .product-item__image.
    """
    try:
        from crawlee.crawlers import BeautifulSoupCrawler, BeautifulSoupCrawlingContext

        found_products: list[dict] = []

        crawler = BeautifulSoupCrawler(
            max_requests_per_crawl=1,
            request_handler_timeout=timedelta(seconds=30),
        )

        @crawler.router.default_handler
        async def denner_handler(context: BeautifulSoupCrawlingContext) -> None:
            context.log.info(f"Scraping Denner: {context.request.url}")
            soup = context.soup
            seen: set[str] = set()

            for item in soup.select(".product-item"):
                name_el = item.select_one(".product-item__title")
                name = name_el.get_text(strip=True) if name_el else ""
                if not name or len(name) < 3 or name.lower() in seen:
                    continue
                seen.add(name.lower())

                # Price: .price-tag__price contains "2.99statt 4.85*"
                # We need to extract just the first price
                price_el = item.select_one(".price-tag__price")
                price = None
                if price_el:
                    price_text = price_el.get_text(strip=True)
                    # Extract first price (current price) before "statt"
                    price_match = PRICE_RE.search(price_text)
                    if price_match:
                        price = float(price_match.group(1).replace(",", "."))
                        if not (PRICE_MIN <= price <= PRICE_MAX):
                            price = None

                # Discount percentage
                discount_el = item.select_one(".price-tag__discount")
                discount = None
                if discount_el:
                    discount = _parse_discount(discount_el.get_text(strip=True))

                # Image
                img_el = item.select_one(".product-item__image")
                img_url = None
                if img_el:
                    img_url = img_el.get("src") or img_el.get("data-src")

                # Subline (description/weight)
                subline_el = item.select_one(".product-item__subline")
                subline = subline_el.get_text(strip=True) if subline_el else ""

                found_products.append(
                    {
                        "retailer": "denner",
                        "name": f"{name} ({subline})" if subline else name,
                        "price": price,
                        "discount_pct": discount,
                        "image_url": img_url,
                        "category": "offer",
                        "region": region,
                    }
                )

        await crawler.run(
            ["https://www.denner.ch/de/aktionen-und-sortiment/aktuelle-aktionen"]
        )

        logger.info(f"Denner: {len(found_products)} products")
        return found_products[:max_items]

    except Exception as e:
        logger.error(f"Denner scraping failed: {e}")
        return []


# ---------------------------------------------------------------------------
# Lidl — Leaflets API (product names) + PDF download for prices
# ---------------------------------------------------------------------------
async def scrape_lidl(max_items: int = 200, region: str = "zurich") -> list[dict]:
    """Scrape Lidl via the Leaflets API with PDF price enrichment.

    Strategy:
    1. Fetch flyer listing page to discover current flyer slugs
    2. Query Leaflets API for each slug → get product names + pdfUrl
    3. Download PDF → try to extract prices via pdfplumber
    4. Merge: API provides accurate names, PDF provides prices
    """
    products: list[dict] = []

    async with httpx.AsyncClient(headers=HEADERS, timeout=120.0) as client:
        resp = await client.get(
            "https://www.lidl.ch/c/de-CH/werbeprospekte-als-pdf/s10019683"
        )
        if not resp.is_success:
            logger.warning(f"Lidl flyer page: HTTP {resp.status_code}")
            return []

        slugs = re.findall(r"/prospekt/([^/]+)/ar/", resp.text)
        seen_slugs: list[str] = []
        for s in slugs:
            if s not in seen_slugs:
                seen_slugs.append(s)
        slugs = seen_slugs

        if not slugs:
            kw = date.today().isocalendar()[1]
            slugs = [f"lidl-aktuell-kw{kw}", f"lidl-aktuell-kw{kw:02d}"]

        logger.info(f"Lidl: found {len(slugs)} flyer slugs: {slugs[:5]}")

        seen: set[str] = set()
        for slug in slugs[:3]:
            try:
                api_url = (
                    f"https://endpoints.leaflets.schwarz/v4/flyer"
                    f"?flyer_identifier={slug}&region_id=0&region_code=0"
                )
                api_resp = await client.get(api_url)
                if not api_resp.is_success:
                    continue

                data = api_resp.json()
                flyer = data.get("flyer", data)

                # Try PDF extraction for prices
                pdf_prices: dict[str, float] = {}
                pdf_url = flyer.get("pdfUrl")
                if pdf_url:
                    try:
                        logger.info(f"Lidl: downloading PDF for '{slug}'")
                        pdf_resp = await client.get(pdf_url)
                        if pdf_resp.is_success and len(pdf_resp.content) > 1000:
                            pdf_products = await extract_products_from_pdf_bytes(
                                pdf_resp.content, "lidl", f"lidl-{slug}.pdf"
                            )
                            for pp in pdf_products:
                                if pp.get("price") and pp.get("name"):
                                    pdf_prices[pp["name"].lower()] = pp["price"]
                            logger.info(
                                f"Lidl: extracted {len(pdf_prices)} prices from PDF"
                            )
                    except Exception as e:
                        logger.warning(f"Lidl PDF download failed: {e}")

                # Extract product names from API (accurate names)
                pages = flyer.get("pages", [])
                for page in pages:
                    for link in page.get("links", []):
                        if link.get("displayType") != "product":
                            continue
                        title = link.get("title", "").strip()
                        if not title or len(title) < 3 or title.lower() in seen:
                            continue
                        seen.add(title.lower())

                        # Try to match price from PDF extraction:
                        # 1. Exact match
                        # 2. Substring match (PDF name contains API name)
                        # 3. First-word match (first significant word)
                        price = pdf_prices.get(title.lower())
                        if price is None:
                            title_l = title.lower()
                            # Substring: check if any PDF name contains this title
                            for pdf_name, pdf_price in pdf_prices.items():
                                if title_l in pdf_name or pdf_name in title_l:
                                    price = pdf_price
                                    break
                        if price is None:
                            # Word overlap: match if ≥2 significant words match
                            # Only use when exactly one PDF entry matches
                            # to avoid attaching wrong prices
                            title_words = {
                                w for w in title.lower().split()
                                if len(w) > 2
                            }
                            if len(title_words) >= 2:
                                candidates = []
                                for pdf_name, pdf_price in pdf_prices.items():
                                    pdf_words = {
                                        w for w in pdf_name.split()
                                        if len(w) > 2
                                    }
                                    overlap = title_words & pdf_words
                                    if len(overlap) >= 2:
                                        candidates.append(pdf_price)
                                if len(candidates) == 1:
                                    price = candidates[0]

                        # Skip non-grocery items (beauty, electronics, etc.)
                        if _NON_GROCERY_KEYWORDS.search(title):
                            continue

                        products.append(
                            {
                                "retailer": "lidl",
                                "name": title,
                                "price": price,
                                "discount_pct": None,
                                "image_url": None,
                                "category": "flyer",
                                "region": "national",
                            }
                        )

                logger.info(
                    f"Lidl flyer '{slug}': {sum(1 for p in products if p.get('price'))} "
                    f"with prices out of {len(products)} products"
                )

            except Exception as e:
                logger.warning(f"Lidl flyer '{slug}' failed: {e}")

    logger.info(f"Lidl: {len(products)} products total")
    return products[:max_items]
