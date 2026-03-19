"""
Swiss Grocery Scraper - Apify Actor
Scrapes Aldi, Migros, Coop, Denner, and Lidl for product offers in Swiss regions.
"""

import asyncio
import logging
import time

import httpx
from apify import Actor

from src.routes import scrape_aldi, scrape_coop, scrape_denner, scrape_lidl, scrape_migros

# Configure root logger so output appears in Apify console
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

SCRAPER_MAP = {
    "aldi": scrape_aldi,
    "migros": scrape_migros,
    "coop": scrape_coop,
    "denner": scrape_denner,
    "lidl": scrape_lidl,
}

ALL_RETAILERS = list(SCRAPER_MAP.keys())

# Region-specific URL overrides for aktionen pages
REGION_URLS = {
    "zurich": {
        "coop": "https://www.coop.ch/de/aktionen.html",
        "migros": "https://www.migros.ch/de/aktionen.html",
        "denner": "https://www.denner.ch/de/aktionen-und-sortiment/aktuelle-aktionen",
        "lidl": "https://www.lidl.ch/c/de-CH/werbeprospekte-als-pdf/s10019683",
    },
    "bern": {
        "coop": "https://www.coop.ch/de/aktionen.html",
        "migros": "https://www.migros.ch/de/aktionen.html",
        "denner": "https://www.denner.ch/de/aktionen-und-sortiment/aktuelle-aktionen",
        "lidl": "https://www.lidl.ch/c/de-CH/werbeprospekte-als-pdf/s10019683",
    },
    "basel": {
        "coop": "https://www.coop.ch/de/aktionen.html",
        "migros": "https://www.migros.ch/de/aktionen.html",
        "denner": "https://www.denner.ch/de/aktionen-und-sortiment/aktuelle-aktionen",
        "lidl": "https://www.lidl.ch/c/de-CH/werbeprospekte-als-pdf/s10019683",
    },
}


async def _scrape_retailer(
    retailer: str, max_items: int, region: str
) -> tuple[str, dict]:
    """Scrape a single retailer and return (retailer, summary)."""
    scraper_fn = SCRAPER_MAP.get(retailer)
    if not scraper_fn:
        logger.warning("Unknown retailer: %s — skipping", retailer)
        return retailer, {"status": "skipped", "reason": "unknown retailer"}

    start = time.monotonic()
    try:
        products = await scraper_fn(max_items=max_items, region=region)
        elapsed = time.monotonic() - start
        logger.info("%s: %d items in %.1fs", retailer, len(products), elapsed)
        return retailer, {
            "status": "ok",
            "items_scraped": len(products),
            "duration_s": round(elapsed, 1),
            "products": products[:max_items],
        }
    except Exception:
        elapsed = time.monotonic() - start
        logger.exception("%s: failed after %.1fs", retailer, elapsed)
        return retailer, {
            "status": "error",
            "duration_s": round(elapsed, 1),
            "products": [],
        }


async def main():
    async with Actor:
        actor_input = await Actor.get_input() or {}
        retailers = actor_input.get("retailers")
        if retailers is None:
            retailers = ALL_RETAILERS
        if isinstance(retailers, str):
            retailers = [retailers]
        # Filter out invalid retailer names
        retailers = [r for r in retailers if r in SCRAPER_MAP]
        if not retailers:
            logger.error("No valid retailers specified")
            await Actor.set_status_message("Error: no valid retailers")
            return
        raw_max = actor_input.get("maxItems")
        max_items = max(1, raw_max if isinstance(raw_max, int) else 200)
        region = actor_input.get("region", "zurich")

        logger.info(
            "Starting scrape for retailers=%s, region=%s", retailers, region
        )
        await Actor.set_status_message(
            f"Scraping {len(retailers)} retailer(s) in {region}"
        )

        start_time = time.monotonic()

        # Run scrapers sequentially — Crawlee crawlers share a default
        # request queue on Apify, so parallel execution causes one crawler
        # to consume URLs intended for another (e.g. Denner's BS4 crawler
        # grabs Migros/Coop URLs before their Playwright crawlers start).
        results = []
        for retailer in retailers:
            result = await _scrape_retailer(retailer, max_items, region)
            results.append(result)

        # Push all products and build summary
        summary: dict[str, dict] = {}
        total_pushed = 0
        for retailer, result in results:
            products = result.pop("products", [])
            summary[retailer] = result
            pushed = 0
            for product in products:
                product["region"] = region
                await Actor.push_data(product)
                pushed += 1
            total_pushed += pushed
            summary[retailer]["items_pushed"] = pushed

        total_elapsed = time.monotonic() - start_time

        kv_store = await Actor.open_key_value_store()
        run_summary = {
            "retailers_requested": retailers,
            "region": region,
            "total_items_pushed": total_pushed,
            "total_duration_s": round(total_elapsed, 1),
            "per_retailer": summary,
        }
        await kv_store.set_value("run-summary", run_summary)

        ok_count = sum(1 for v in summary.values() if v.get("status") == "ok")
        finished_msg = (
            f"Done: {total_pushed} items from "
            f"{ok_count}/{len(retailers)} retailers "
            f"({region}) in {total_elapsed:.0f}s"
        )
        logger.info(finished_msg)
        logger.info("Per-retailer summary: %s", summary)

        # Webhook notification — notify backend to trigger Qdrant ingestion
        webhook_url = actor_input.get("webhookUrl")
        if webhook_url and total_pushed > 0:
            await Actor.set_status_message("Sending webhook notification...")
            webhook_key = actor_input.get("webhookApiKey", "")
            headers: dict[str, str] = {"Content-Type": "application/json"}
            if webhook_key:
                headers["Authorization"] = f"Bearer {webhook_key}"
            try:
                async with httpx.AsyncClient(timeout=30.0) as http:
                    resp = await http.post(
                        webhook_url,
                        headers=headers,
                        json={
                            "event": "scrape_completed",
                            "total_items": total_pushed,
                            "region": region,
                            "retailers": retailers,
                            "duration_s": round(total_elapsed, 1),
                        },
                    )
                    logger.info("Webhook response: %d", resp.status_code)
            except Exception as e:
                logger.warning("Webhook notification failed: %s", e)

        await Actor.set_status_message(finished_msg)


if __name__ == "__main__":
    asyncio.run(main())
