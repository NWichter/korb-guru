"""Coop store locations via VST API."""
import logging

from crawler.smartcart.models.location import StoreLocation
from crawler.smartcart.utils.http import fetch_json
from crawler.smartcart.utils.geo import filter_zurich_stores

logger = logging.getLogger(__name__)

ZURICH_LAT = 47.3769
ZURICH_LNG = 8.5417
API_BASE = "https://www.coop.ch/de/unternehmen/standorte-und-oeffnungszeiten.getvstlist.json"


async def scrape_locations() -> list[StoreLocation]:
    logger.info("Fetching Coop locations from VST API...")
    params = {
        "lat": ZURICH_LAT,
        "lng": ZURICH_LNG,
        "start": 1,
        "end": 2000,
        "filterFormat": "retail",
        "filterAttribute": "",
        "filterOpen": "false",
        "gasIndex": 0,
    }
    url = f"{API_BASE}?{'&'.join(f'{k}={v}' for k, v in params.items())}"
    data = await fetch_json(url)

    all_stores = data.get("vstList", [])
    logger.info(f"Fetched {len(all_stores)} Coop retail stores")

    mapped = []
    for s in all_stores:
        geo = s.get("geoKoordinaten", {})
        mapped.append({
            "chain": "Coop",
            "name": s.get("namePublic") or s.get("nameInternal") or s.get("name", ""),
            "address": f"{s.get('strasse', '')} {s.get('hausnummer', '')}".strip(),
            "plz": str(s.get("plz", "")),
            "city": s.get("ort", ""),
            "lat": geo.get("latitude"),
            "lon": geo.get("longitude"),
        })

    filtered = filter_zurich_stores(mapped)
    stores = [StoreLocation(**{k: v for k, v in s.items()}) for s in filtered]
    logger.info(f"Filtered to {len(stores)} Zürich-area stores")
    return stores
