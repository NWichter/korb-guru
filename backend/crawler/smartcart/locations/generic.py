"""Generic store location scraper using Playwright (for Aldi, Lidl)."""
import logging

from crawler.smartcart.models.location import StoreLocation

logger = logging.getLogger(__name__)

STORE_FINDERS = {
    "aldi": {
        "name": "Aldi Suisse",
        "url": "https://www.aldi-suisse.ch/de/filialen-und-oeffnungszeiten.html",
    },
    "lidl": {
        "name": "Lidl",
        "url": "https://www.lidl.ch/de/filialsuche",
    },
}


async def scrape_locations(chain_key: str) -> list[StoreLocation]:
    config = STORE_FINDERS.get(chain_key)
    if not config:
        logger.error(f"No store finder config for: {chain_key}")
        return []

    logger.info(f"Fetching {config['name']} locations via Playwright...")

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.warning("Playwright not installed, returning empty list")
        return []

    stores = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            await page.goto(config["url"], wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(3000)

            # Search for Zürich
            search_input = await page.query_selector(
                'input[type="search"], input[type="text"], input[placeholder*="PLZ"], input[placeholder*="Ort"]'
            )
            if search_input:
                await search_input.fill("8001 Zürich")
                await page.keyboard.press("Enter")
                await page.wait_for_timeout(3000)

            # Extract store data
            store_data = await page.evaluate("""() => {
                const stores = [];
                const selectors = '[class*="store-item"], [class*="store-result"], [class*="location-item"], [class*="filiale"], [class*="market"]';
                document.querySelectorAll(selectors).forEach(el => {
                    const name = (el.querySelector('h2, h3, h4, [class*="name"], [class*="title"]') || {}).textContent?.trim();
                    const address = (el.querySelector('[class*="address"], address, [class*="street"]') || {}).textContent?.trim();
                    const hours = (el.querySelector('[class*="hour"], [class*="opening"], [class*="zeit"]') || {}).textContent?.trim();
                    if (name) stores.push({name, address: address || '', openingHours: hours || ''});
                });
                return stores;
            }""")

            import re
            for s in store_data:
                plz_match = re.search(r"(\d{4})\s+([\w\u00C0-\u017F]+)", s.get("address", ""))
                stores.append(StoreLocation(
                    chain=config["name"],
                    name=s["name"],
                    address=s.get("address", ""),
                    plz=plz_match.group(1) if plz_match else "",
                    city=plz_match.group(2) if plz_match else "",
                    opening_hours=s.get("openingHours"),
                ))
        finally:
            await browser.close()

    logger.info(f"Found {len(stores)} {config['name']} stores")
    return stores
