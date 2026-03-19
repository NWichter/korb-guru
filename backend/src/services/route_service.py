"""Route optimization service — nearest-neighbor heuristic with OSRM integration."""

import logging
import math
from collections import Counter

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.product import Product
from ..models.store import Store

logger = logging.getLogger(__name__)

OSRM_BASE_URL = "http://router.project-osrm.org"

# Map transport mode names to OSRM profile names
OSRM_PROFILES: dict[str, str] = {
    "driving": "car",
    "cycling": "bike",
    "walking": "foot",
}


async def _osrm_route_leg(
    client: httpx.AsyncClient,
    profile: str,
    lat1: float,
    lng1: float,
    lat2: float,
    lng2: float,
) -> tuple[float, float] | None:
    """Fetch distance (m) and duration (s) for a single leg from OSRM.

    Returns None if the request fails or OSRM cannot find a route.
    """
    coords = f"{lng1},{lat1};{lng2},{lat2}"
    url = f"{OSRM_BASE_URL}/route/v1/{profile}/{coords}?overview=false"
    try:
        resp = await client.get(url, timeout=5.0)
        if resp.status_code != 200:
            logger.warning(
                "OSRM %d for (%f,%f)->(%f,%f)",
                resp.status_code,
                lat1,
                lng1,
                lat2,
                lng2,
            )
            return None
        data = resp.json()
        if data.get("code") != "Ok" or not data.get("routes"):
            return None
        route = data["routes"][0]
        return route["distance"], route["duration"]
    except Exception as exc:
        logger.warning("OSRM request failed, falling back to Haversine: %s", exc)
        return None


async def optimize_route(
    selected_shops: list[str],
    time_limit: int,
    session: AsyncSession,
    start_lat: float | None = None,
    start_lng: float | None = None,
    transport_mode: str = "walking",
) -> dict:
    stores_result = await session.execute(
        select(Store).where(Store.name.in_(selected_shops))
    )
    stores = stores_result.scalars().all()

    # Log partial lookup misses instead of silently dropping
    found_names = {s.name for s in stores}
    missing = [name for name in selected_shops if name not in found_names]
    if missing:
        logger.warning("Store lookup missed %d shops: %s", len(missing), missing)

    # Warn when a store name matches multiple rows (name is not unique)
    name_counts = Counter(s.name for s in stores)
    ambiguous = {name: count for name, count in name_counts.items() if count > 1}
    if ambiguous:
        logger.warning(
            "Ambiguous store name lookup — multiple stores share the same name: %s",
            ambiguous,
        )

    if not stores:
        stops = []
        for i, shop in enumerate(selected_shops):
            stops.append(
                {
                    "name": shop,
                    "task": "Buy fresh ingredients" if i == 0 else "Rest of items",
                    "distance": f"{0.8 + i * 0.7:.1f}km",
                    "latitude": None,
                    "longitude": None,
                }
            )
        return {
            "saved": 0.0,
            "time": max(0, time_limit - 5),
            "stops": stops,
            "legs": [],
            "total_distance_m": 0.0,
            "total_duration_min": 0.0,
        }

    # Order stores using nearest-neighbor starting from user location if provided
    ordered = _nearest_neighbor_order(list(stores), start_lat, start_lng)

    # Build waypoint list: start location (if given) + ordered stores
    waypoints: list[tuple[float, float, str | None]] = []
    if start_lat is not None and start_lng is not None:
        waypoints.append((start_lat, start_lng, None))
    for store in ordered:
        waypoints.append((store.latitude, store.longitude, store.name))

    # Fetch OSRM distances for each leg
    profile = OSRM_PROFILES.get(transport_mode, "foot")
    legs: list[dict] = []
    total_distance_m = 0.0
    total_duration_s = 0.0

    async with httpx.AsyncClient() as client:
        for i in range(1, len(waypoints)):
            lat1, lng1, from_name = waypoints[i - 1]
            lat2, lng2, to_name = waypoints[i]

            osrm_result = await _osrm_route_leg(client, profile, lat1, lng1, lat2, lng2)
            if osrm_result is not None:
                distance_m, duration_s = osrm_result
            else:
                # Fallback to Haversine
                distance_km = _distance_km(lat1, lng1, lat2, lng2)
                distance_m = distance_km * 1000
                # Estimate duration based on transport mode
                speed_kmh = {"driving": 40.0, "cycling": 15.0, "walking": 5.0}.get(
                    transport_mode, 5.0
                )
                duration_s = (distance_km / speed_kmh) * 3600

            total_distance_m += distance_m
            total_duration_s += duration_s

            legs.append(
                {
                    "from_store": from_name,
                    "to_store": to_name,
                    "distance_m": round(distance_m, 1),
                    "duration_min": round(duration_s / 60, 1),
                    "transport_mode": transport_mode,
                }
            )

    # Collect product info per store brand
    store_brands = {s.name: s.brand for s in ordered}
    unique_brands = list(set(store_brands.values()))
    products_by_brand: dict[str, list[dict]] = {b: [] for b in unique_brands}
    if unique_brands:
        products_result = await session.execute(
            select(Product).where(Product.retailer.in_(unique_brands))
        )
        for p in products_result.scalars().all():
            products_by_brand[p.retailer].append(
                {
                    "name": p.name,
                    "price": float(p.price) if p.price is not None else None,
                    "category": p.category,
                }
            )

    # Build stops with product information
    stops = []
    tasks = ["Buy fresh ingredients", "Buy pantry staples", "Rest of items"]
    for i, store in enumerate(ordered):
        # Distance from previous store (or start)
        leg_distance = legs[i]["distance_m"] if i < len(legs) else 0.0
        brand = store_brands[store.name]
        store_products = products_by_brand.get(brand, [])

        stops.append(
            {
                "name": store.name,
                "task": tasks[min(i, len(tasks) - 1)],
                "distance": f"{leg_distance / 1000:.1f}km",
                "latitude": store.latitude,
                "longitude": store.longitude,
                "products": store_products[:20],  # Limit to avoid huge payloads
            }
        )

    total_duration_min = round(total_duration_s / 60, 1)
    estimated_time = max(0, min(time_limit - 5, len(stops) * 12))

    return {
        "saved": 0.0,
        "time": estimated_time,
        "stops": stops,
        "legs": legs,
        "total_distance_m": round(total_distance_m, 1),
        "total_duration_min": total_duration_min,
    }


def _nearest_neighbor_order(
    stores: list,
    start_lat: float | None = None,
    start_lng: float | None = None,
) -> list:
    if len(stores) <= 1:
        return list(stores)

    remaining = sorted(stores, key=lambda s: str(s.id))

    if start_lat is not None and start_lng is not None:
        # Start from the store nearest to the user's location
        nearest_to_start = min(
            remaining,
            key=lambda s: _distance_km(start_lat, start_lng, s.latitude, s.longitude),
        )
        remaining.remove(nearest_to_start)
        ordered = [nearest_to_start]
    else:
        ordered = [remaining.pop(0)]

    while remaining:
        current = ordered[-1]
        nearest = min(
            remaining,
            key=lambda s: _distance_km(
                current.latitude, current.longitude, s.latitude, s.longitude
            ),
        )
        remaining.remove(nearest)
        ordered.append(nearest)
    return ordered


def _distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    earth_radius_km = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return earth_radius_km * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
