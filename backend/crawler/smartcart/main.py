"""
SmartCart Crawler - CLI Orchestrator
Swiss grocery retailer scraper for Zürich (5 retailers)

Usage:
    python -m crawler.smartcart.main                    # run all
    python -m crawler.smartcart.main --prospekte        # prospekt scrapers only
    python -m crawler.smartcart.main --locations        # location scrapers only
    python -m crawler.smartcart.main --chain=aldi       # single chain
    python -m crawler.smartcart.main --ingest           # also ingest to Qdrant
"""
import argparse
import asyncio
import json
import logging
import time

from crawler.smartcart.config import RETAILERS, LOCATIONS_DIR, PROSPEKTE_DIR
from crawler.smartcart.scrapers.aldi import AldiScraper
from crawler.smartcart.scrapers.migros import MigrosScraper
from crawler.smartcart.scrapers.denner import DennerScraper
from crawler.smartcart.scrapers.coop import CoopScraper
from crawler.smartcart.scrapers.lidl import LidlScraper
from crawler.smartcart.locations import migros as loc_migros, coop as loc_coop, denner as loc_denner
from crawler.smartcart.locations.generic import scrape_locations as generic_locations

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("smartcart")

SCRAPER_MAP = {
    "aldi": AldiScraper,
    "migros": MigrosScraper,
    "denner": DennerScraper,
    "coop": CoopScraper,
    "lidl": LidlScraper,
}

LOCATION_MAP = {
    "migros": loc_migros.scrape_locations,
    "coop": loc_coop.scrape_locations,
    "denner": loc_denner.scrape_locations,
    "aldi": lambda: generic_locations("aldi"),
    "lidl": lambda: generic_locations("lidl"),
}


async def run_prospekt(chain: str) -> dict:
    start = time.time()
    scraper_cls = SCRAPER_MAP.get(chain)
    if not scraper_cls:
        return {"chain": chain, "ok": False, "error": f"No scraper for {chain}", "elapsed": 0}
    try:
        scraper = scraper_cls()
        result = await scraper.scrape()
        elapsed = round(time.time() - start, 1)
        return {"chain": chain, "ok": True, "elapsed": elapsed, "result": result}
    except Exception as e:
        elapsed = round(time.time() - start, 1)
        return {"chain": chain, "ok": False, "error": str(e), "elapsed": elapsed}


async def run_location(chain: str) -> dict:
    start = time.time()
    fn = LOCATION_MAP.get(chain)
    if not fn:
        return {"chain": chain, "ok": False, "error": f"No location scraper for {chain}", "elapsed": 0}
    try:
        stores = await fn()
        elapsed = round(time.time() - start, 1)
        # Save to JSON
        LOCATIONS_DIR.mkdir(parents=True, exist_ok=True)
        filepath = LOCATIONS_DIR / f"{chain}.json"
        filepath.write_text(json.dumps([s.model_dump() for s in stores], indent=2, ensure_ascii=False))
        return {"chain": chain, "ok": True, "elapsed": elapsed, "count": len(stores)}
    except Exception as e:
        elapsed = round(time.time() - start, 1)
        return {"chain": chain, "ok": False, "error": str(e), "elapsed": elapsed}


async def main():
    parser = argparse.ArgumentParser(description="SmartCart Swiss Grocery Crawler")
    parser.add_argument("--prospekte", action="store_true", help="Run prospekt scrapers only")
    parser.add_argument("--locations", action="store_true", help="Run location scrapers only")
    parser.add_argument(
        "--chain", type=str, choices=list(RETAILERS.keys()),
        help="Run single chain only",
    )
    parser.add_argument("--ingest", action="store_true", help="Ingest products to Qdrant")
    args = parser.parse_args()

    run_prospekte = not args.locations
    run_locations = not args.prospekte

    chains = [args.chain] if args.chain else list(RETAILERS.keys())

    print("\n" + "=" * 55)
    print("  SmartCart Crawler - Raum Zürich (5 Retailers)")
    print("=" * 55 + "\n")

    all_products = []

    if run_prospekte:
        print("-- Prospekt Scrapers " + "-" * 34 + "\n")
        # Run all prospekt scrapers in parallel
        tasks = [run_prospekt(c) for c in chains]
        results = await asyncio.gather(*tasks)
        for r in results:
            name = RETAILERS.get(r["chain"], {}).get("name", r["chain"])
            icon = "OK" if r["ok"] else "FAIL"
            print(f"  [{icon}] {name:<25} {r['elapsed']}s")
            if r["ok"] and hasattr(r.get("result"), "products"):
                product_count = len(r["result"].products)
                if product_count == 0:
                    logger.warning(f"ALERT: {name} returned 0 products — selectors may be broken!")
                all_products.extend(r["result"].products)
        print()

    if run_locations:
        print("-- Location Scrapers " + "-" * 34 + "\n")
        tasks = [run_location(c) for c in chains]
        results = await asyncio.gather(*tasks)
        for r in results:
            name = RETAILERS.get(r["chain"], {}).get("name", r["chain"])
            icon = "OK" if r["ok"] else "FAIL"
            count = f"({r.get('count', '?')} stores)" if r["ok"] else f"ERROR: {r.get('error', '')}"
            print(f"  [{icon}] {name:<25} {r['elapsed']}s  {count}")
        print()

    if args.ingest and all_products:
        print(f"\nIngesting {len(all_products)} products to Qdrant...")
        from crawler.smartcart.ingest.qdrant_ingest import ingest_to_qdrant
        ingest_to_qdrant(all_products)
        print("Ingestion complete.\n")

    from crawler.smartcart.utils.http import close_client
    await close_client()


if __name__ == "__main__":
    asyncio.run(main())
