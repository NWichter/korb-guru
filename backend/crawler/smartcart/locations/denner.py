"""Denner store locations via public API."""
import logging

from crawler.smartcart.models.location import StoreLocation
from crawler.smartcart.utils.http import fetch_json
from crawler.smartcart.utils.geo import filter_zurich_stores

logger = logging.getLogger(__name__)

API_URL = "https://www.denner.ch/api/store/list"


async def scrape_locations() -> list[StoreLocation]:
    logger.info("Fetching Denner locations...")
    all_hits = []
    page = 1
    total_pages = 1

    while page <= total_pages:
        data = await fetch_json(f"{API_URL}?locale=de&page={page}")
        inner = data.get("data", data)
        total_pages = inner.get("totalPages", 1)
        all_hits.extend(inner.get("hits", []))
        page += 1
        if not inner.get("hits"):
            break

    logger.info(f"Fetched {len(all_hits)} Denner stores total")

    mapped = []
    for s in all_hits:
        geo = s.get("_geo", {})
        mapped.append({
            "chain": "Denner",
            "name": s.get("displayName") or s.get("name") or f"Denner {s.get('city', '')}",
            "address": s.get("address", ""),
            "plz": str(s.get("zip", "")),
            "city": s.get("city", ""),
            "lat": geo.get("lat"),
            "lon": geo.get("lng"),
        })

    filtered = filter_zurich_stores(mapped)
    stores = [StoreLocation(**{k: v for k, v in s.items()}) for s in filtered]
    logger.info(f"Filtered to {len(stores)} Zürich-area stores")
    return stores
