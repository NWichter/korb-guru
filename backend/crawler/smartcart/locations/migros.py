"""Migros store locations via Overpass API (OpenStreetMap)."""
import logging

from crawler.smartcart.config import ZURICH_BBOX
from crawler.smartcart.models.location import StoreLocation
from crawler.smartcart.utils.http import fetch_text

logger = logging.getLogger(__name__)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"


async def scrape_locations() -> list[StoreLocation]:
    logger.info("Fetching Migros locations from Overpass API...")
    bbox = f"{ZURICH_BBOX['lat_min']},{ZURICH_BBOX['lon_min']},{ZURICH_BBOX['lat_max']},{ZURICH_BBOX['lon_max']}"
    query = f'[out:json][timeout:60];(node["shop"="supermarket"]["name"="Migros"]({bbox});way["shop"="supermarket"]["name"="Migros"]({bbox}););out center;'

    import httpx
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            OVERPASS_URL,
            data={"data": query},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()
        data = resp.json()

    elements = data.get("elements", [])
    logger.info(f"Overpass returned {len(elements)} Migros stores")

    stores = []
    for e in elements:
        tags = e.get("tags", {})
        lat = e.get("lat") or (e.get("center", {}).get("lat"))
        lon = e.get("lon") or (e.get("center", {}).get("lon"))
        stores.append(StoreLocation(
            chain="Migros",
            name=tags.get("alt_name") or tags.get("branch") or f"Migros {tags.get('addr:city', '')}".strip(),
            address=f"{tags.get('addr:street', '')} {tags.get('addr:housenumber', '')}".strip(),
            plz=tags.get("addr:postcode", ""),
            city=tags.get("addr:city", ""),
            lat=lat,
            lon=lon,
            opening_hours=tags.get("opening_hours"),
        ))
    return stores
