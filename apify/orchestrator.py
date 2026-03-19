"""
Apify Crawler Orchestrator

Runs the custom swiss-grocery-scraper Actor and ingests results
via the FastAPI /ingest endpoint (Postgres + Qdrant).

Usage:
    python -m crawler.apify.orchestrator
    python -m crawler.apify.orchestrator --chain=aldi
    python -m crawler.apify.orchestrator --ingest
    python -m crawler.apify.orchestrator --ingest --ingest-url=https://api.korb.guru
"""

import argparse
import logging
import os
import time

import httpx
from apify_client import ApifyClient

from crawler.apify.config import (
    ALL_RETAILERS,
    APIFY_TOKEN,
    CUSTOM_ACTOR_ID,
    CUSTOM_ACTOR_INPUT,
    ACTOR_TIMEOUT_SECS,
    MAX_RETRIES,
)
from crawler.apify.ingest.transform import normalize_items

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("apify-orchestrator")


def run_actor_with_retry(
    client: ApifyClient,
    actor_id: str,
    run_input: dict,
    retries: int = MAX_RETRIES,
) -> list[dict]:
    """Run an Apify Actor with retry logic."""
    for attempt in range(1, retries + 1):
        try:
            logger.info(
                "Running Actor '%s' (attempt %d/%d)...",
                actor_id,
                attempt,
                retries,
            )
            start = time.time()

            run = client.actor(actor_id).call(
                run_input=run_input,
                timeout_secs=ACTOR_TIMEOUT_SECS,
            )
            items = client.dataset(run["defaultDatasetId"]).list_items().items
            elapsed = round(time.time() - start, 1)
            logger.info("  Got %d items in %ss", len(items), elapsed)
            return items

        except Exception as e:
            logger.warning("  Attempt %d failed: %s", attempt, e)
            if attempt < retries:
                wait = 5 * attempt
                logger.info("  Retrying in %ds...", wait)
                time.sleep(wait)
            else:
                raise RuntimeError(
                    f"Actor '{actor_id}' failed after {retries} attempts"
                ) from e
    return []


def ingest_via_api(
    items: list[dict],
    base_url: str = "http://localhost:8000",
    api_key: str | None = None,
    region: str = "zurich",
) -> dict:
    """POST normalized products to the /ingest API endpoint.

    This writes to both PostgreSQL AND Qdrant (via the backend).
    """
    records = []
    for item in items:
        records.append({
            "retailer": item.get("retailer", ""),
            "name": item.get("name", ""),
            "description": item.get("description"),
            "price": item.get("price"),
            "originalPrice": item.get("original_price"),
            "discountPct": item.get("discount_pct"),
            "category": item.get("category"),
            "imageUrl": item.get("image_url"),
            "region": region,
        })

    headers: dict[str, str] = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "source": "apify",
        "region": region,
        "records": records,
    }

    with httpx.Client(timeout=60.0) as http:
        resp = http.post(f"{base_url}/ingest", headers=headers, json=payload)
        resp.raise_for_status()
        result = resp.json()
        logger.info("Ingestion response: %s", result)
        return result


def main():
    parser = argparse.ArgumentParser(description="Apify Crawler Orchestrator")
    parser.add_argument(
        "--chain",
        type=str,
        help=f"Run single chain only ({'/'.join(ALL_RETAILERS)})",
    )
    parser.add_argument(
        "--ingest",
        action="store_true",
        help="Ingest results via /ingest API (Postgres + Qdrant)",
    )
    parser.add_argument(
        "--ingest-url",
        type=str,
        default="http://localhost:8000",
        help="Backend API base URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        help="Ingest API key (or set INGEST_API_KEY env var)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be run without executing",
    )
    args = parser.parse_args()

    if not APIFY_TOKEN:
        logger.error("APIFY_TOKEN not set. Export it or add to .env")
        return

    client = ApifyClient(APIFY_TOKEN)

    print("\n" + "=" * 55)
    print("  Apify Crawler Orchestrator")
    print("=" * 55 + "\n")

    # Determine which retailers to scrape
    if args.chain:
        if args.chain not in ALL_RETAILERS:
            logger.error(
                "Unknown chain '%s'. Available: %s", args.chain, ALL_RETAILERS
            )
            return
        retailers = [args.chain]
    else:
        retailers = ALL_RETAILERS

    if args.dry_run:
        print("DRY RUN - would execute:")
        print(f"  - Actor: {CUSTOM_ACTOR_ID}")
        print(f"  - Retailers: {retailers}")
        print(f"  - Max items per retailer: {CUSTOM_ACTOR_INPUT['maxItems']}")
        return

    # Build input for this run
    run_input = {**CUSTOM_ACTOR_INPUT, "retailers": retailers}

    items = run_actor_with_retry(client, CUSTOM_ACTOR_ID, run_input)
    normalized = normalize_items(items, "custom")

    print(f"\nTotal items collected: {len(normalized)}")

    if args.ingest and normalized:
        api_key = args.api_key or os.getenv("INGEST_API_KEY")
        print(f"\nIngesting {len(normalized)} items via {args.ingest_url}/ingest...")
        result = ingest_via_api(normalized, args.ingest_url, api_key)
        print(f"Ingestion complete: {result}")
    elif not normalized:
        print("\nNo items to ingest.")


if __name__ == "__main__":
    main()
