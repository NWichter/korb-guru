"""Scraper health check: verify CSS selectors still match on live retailer pages."""
import asyncio
import json
import logging
import sys
from datetime import date

from crawler.smartcart.monitoring.selectors import SELECTOR_REGISTRY
from crawler.smartcart.utils.http import fetch_text, head_check, close_client

logger = logging.getLogger(__name__)


async def check_retailer(name: str, config: dict) -> dict:
    """Check if selectors still match for a retailer."""
    result = {"retailer": name, "status": "ok", "details": {}}

    try:
        if config["method"] == "head_check":
            # Aldi: check if PDF URL exists for current week
            today = date.today()
            kw = today.isocalendar()[1]
            url = f"https://s7g10.scene7.com/is/content/aldi/AW_KW{kw}_Sp01_DE_FINAL"
            exists = await head_check(url)
            result["details"]["pdf_exists"] = exists
            if not exists:
                result["status"] = "warning"
                result["message"] = f"No PDF found for KW{kw}"
            return result

        if config["method"] == "playwright":
            try:
                from playwright.async_api import async_playwright
            except ImportError:
                result["status"] = "skip"
                result["message"] = "Playwright not installed"
                return result

            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True)
                try:
                    page = await browser.new_page()
                    await page.goto(config["url"], wait_until="networkidle", timeout=30000)
                    await page.wait_for_timeout(3000)

                    for selector_name, selector in config.get("selectors", {}).items():
                        count = await page.evaluate(
                            f"document.querySelectorAll('{selector}').length"
                        )
                        result["details"][selector_name] = count
                finally:
                    await browser.close()

        elif config["method"] == "beautifulsoup":
            from bs4 import BeautifulSoup

            html = await fetch_text(config["url"])
            soup = BeautifulSoup(html, "html.parser")
            main_el = soup.find("main") or soup

            for selector_name, selector in config.get("selectors", {}).items():
                count = len(main_el.select(selector))
                result["details"][selector_name] = count

        # Check minimum expectations
        min_expected = config.get("min_expected", 1)
        card_count = result["details"].get("product_cards", result["details"].get("pdf_links", 0))
        if card_count < min_expected:
            result["status"] = "critical"
            result["message"] = f"Found {card_count} elements (expected >= {min_expected})"

    except Exception as e:
        result["status"] = "error"
        result["message"] = str(e)

    return result


async def run_health_check() -> list[dict]:
    """Run health checks on all retailers and return results."""
    results = []
    for name, config in SELECTOR_REGISTRY.items():
        logger.info(f"Checking {name}...")
        result = await check_retailer(name, config)
        results.append(result)
        status_icon = {"ok": "+", "warning": "~", "critical": "!", "error": "X", "skip": "-"}
        logger.info(f"  [{status_icon.get(result['status'], '?')}] {name}: {result['status']} {result.get('message', '')}")
    await close_client()
    return results


async def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    print("=" * 60)
    print("korb.guru Scraper Health Check")
    print("=" * 60)

    results = await run_health_check()

    print()
    print(f"{'Retailer':<12} {'Status':<10} {'Details'}")
    print("-" * 60)
    for r in results:
        details = json.dumps(r.get("details", {})) if r.get("details") else r.get("message", "")
        print(f"{r['retailer']:<12} {r['status']:<10} {details}")

    critical = [r for r in results if r["status"] == "critical"]
    if critical:
        print(f"\nCRITICAL: {len(critical)} retailer(s) have broken selectors!")
        sys.exit(1)

    errors = [r for r in results if r["status"] == "error"]
    if errors:
        print(f"\nERROR: {len(errors)} retailer(s) could not be checked.")
        sys.exit(2)

    print("\nAll retailers OK.")
