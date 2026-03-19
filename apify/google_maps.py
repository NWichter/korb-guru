"""
Google Maps Store Discovery

Runs the compass/crawler-google-places Apify actor to discover
grocery store locations, then ingests them via POST /api/v1/stores/ingest.

Usage:
    python -m crawler.apify.google_maps
    python -m crawler.apify.google_maps --brand=migros
    python -m crawler.apify.google_maps --dry-run
    python -m crawler.apify.google_maps --ingest-url=http://localhost:8000
"""

import argparse
import json
import logging
import time

import httpx
from apify_client import ApifyClient

from crawler.apify.config import APIFY_TOKEN

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("google-maps")

GOOGLE_MAPS_ACTOR = "compass/crawler-google-places"

# Search queries per brand — these are the exact store names Google Maps expects
BRAND_SEARCHES: dict[str, list[str]] = {
    "migros": ["Migros Supermarkt"],
    "coop": ["Coop Supermarkt"],
    "aldi": ["Aldi Suisse"],
    "lidl": ["Lidl Schweiz"],
    "denner": ["Denner"],
}

# Default: Zürich area (center + ~15km radius via zoom)
DEFAULT_LOCATION = "Zürich, Schweiz"
DEFAULT_MAX_PER_SEARCH = 50


def run_google_maps(
    brands: list[str],
    location: str = DEFAULT_LOCATION,
    max_per_search: int = DEFAULT_MAX_PER_SEARCH,
    language: str = "de",
) -> list[dict]:
    """Run Google Maps actor and return raw place data."""
    if not APIFY_TOKEN:
        raise RuntimeError("APIFY_TOKEN not set")

    client = ApifyClient(APIFY_TOKEN)
    all_places: list[dict] = []

    for brand in brands:
        searches = BRAND_SEARCHES.get(brand)
        if not searches:
            logger.warning("Unknown brand: %s — skipping", brand)
            continue

        run_input = {
            "searchStringsArray": searches,
            "locationQuery": location,
            "maxCrawledPlacesPerSearch": max_per_search,
            "language": language,
            "skipClosedPlaces": True,
        }

        logger.info(
            "Running Google Maps actor for %s in %s (max %d)...",
            brand,
            location,
            max_per_search,
        )
        start = time.time()

        try:
            run = client.actor(GOOGLE_MAPS_ACTOR).call(
                run_input=run_input,
                timeout_secs=300,
            )
            items = client.dataset(run["defaultDatasetId"]).list_items().items
            elapsed = round(time.time() - start, 1)
            logger.info("  %s: %d places in %ss", brand, len(items), elapsed)
            all_places.extend(items)
        except Exception:
            logger.exception("  %s: Google Maps actor failed", brand)

    return all_places


def transform_places(raw_places: list[dict]) -> list[dict]:
    """Transform Google Maps actor output to our API format."""
    transformed = []
    seen_place_ids: set[str] = set()

    for place in raw_places:
        place_id = place.get("placeId")
        if not place_id or place_id in seen_place_ids:
            continue
        seen_place_ids.add(place_id)

        location = place.get("location", {})
        lat = location.get("lat") if isinstance(location, dict) else None
        lng = location.get("lng") if isinstance(location, dict) else None

        if lat is None or lng is None:
            continue

        transformed.append({
            "title": place.get("title", ""),
            "address": place.get("address"),
            "lat": lat,
            "lng": lng,
            "placeId": place_id,
            "phone": place.get("phone"),
            "website": place.get("website"),
            "totalScore": place.get("totalScore"),
            "categoryName": place.get("categoryName"),
            "openingHours": place.get("openingHours"),
        })

    return transformed


def ingest_to_api(
    places: list[dict],
    base_url: str = "http://localhost:8000",
    api_key: str | None = None,
    region: str = "zurich",
) -> dict:
    """POST transformed places to the store ingest endpoint."""
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {"places": places, "region": region}

    with httpx.Client(timeout=30.0) as client:
        resp = client.post(
            f"{base_url}/api/v1/stores/ingest",
            headers=headers,
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()


def main():
    parser = argparse.ArgumentParser(description="Google Maps Store Discovery")
    parser.add_argument(
        "--brand",
        type=str,
        help="Single brand to search (migros/coop/aldi/lidl/denner)",
    )
    parser.add_argument(
        "--location",
        type=str,
        default=DEFAULT_LOCATION,
        help=f"Location query (default: {DEFAULT_LOCATION})",
    )
    parser.add_argument(
        "--max-per-search",
        type=int,
        default=DEFAULT_MAX_PER_SEARCH,
        help=f"Max places per search (default: {DEFAULT_MAX_PER_SEARCH})",
    )
    parser.add_argument(
        "--ingest-url",
        type=str,
        default="http://localhost:8000",
        help="Backend API base URL for ingestion",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        help="Ingest API key (or set INGEST_API_KEY env var)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch from Google Maps but don't ingest",
    )
    args = parser.parse_args()

    brands = [args.brand] if args.brand else list(BRAND_SEARCHES.keys())

    # Fetch from Google Maps
    raw = run_google_maps(brands, args.location, args.max_per_search)
    places = transform_places(raw)

    print(f"\nFound {len(places)} unique places across {len(brands)} brand(s)")

    if args.dry_run:
        for p in places[:10]:
            print(f"  {p['title']} — {p['address']}")
        if len(places) > 10:
            print(f"  ... and {len(places) - 10} more")
        return

    if not places:
        print("No places found — nothing to ingest")
        return

    # Ingest to API
    import os

    api_key = args.api_key or os.getenv("INGEST_API_KEY")
    result = ingest_to_api(places, args.ingest_url, api_key)
    print(f"Ingestion result: {json.dumps(result, indent=2)}")


if __name__ == "__main__":
    main()
