"""Geographic filtering for Zürich area."""
from crawler.smartcart.config import ZURICH_BBOX, ZURICH_PLZ_RANGES


def is_in_zurich_area(lat: float, lon: float) -> bool:
    return (
        ZURICH_BBOX["lat_min"] <= lat <= ZURICH_BBOX["lat_max"]
        and ZURICH_BBOX["lon_min"] <= lon <= ZURICH_BBOX["lon_max"]
    )


def is_zurich_plz(plz: str | int) -> bool:
    try:
        n = int(plz)
    except (ValueError, TypeError):
        return False
    return any(lo <= n <= hi for lo, hi in ZURICH_PLZ_RANGES)


def filter_zurich_stores(stores: list[dict], lat_key: str = "lat", lon_key: str = "lon") -> list[dict]:
    return [
        s for s in stores
        if (s.get(lat_key) and s.get(lon_key) and is_in_zurich_area(s[lat_key], s[lon_key]))
        or (s.get("plz") and is_zurich_plz(s["plz"]))
    ]
