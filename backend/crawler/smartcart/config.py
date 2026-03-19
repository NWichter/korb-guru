from pathlib import Path

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"
PROSPEKTE_DIR = OUTPUT_DIR / "prospekte"
LOCATIONS_DIR = OUTPUT_DIR / "locations"

ZURICH_BBOX = {
    "lat_min": 47.20,
    "lat_max": 47.60,
    "lon_min": 8.35,
    "lon_max": 8.85,
}

ZURICH_PLZ_RANGES = [
    (8000, 8099),
    (8100, 8197),
    (8200, 8499),
    (8500, 8599),
    (8600, 8967),
]

# Price bounds for Swiss grocery products (CHF)
PRICE_MIN = 0.10
PRICE_MAX = 500.0

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept-Language": "de-CH,de;q=0.9,en;q=0.8",
}

RETAILERS = {
    "aldi": {"name": "Aldi Suisse", "tier": 1},
    "denner": {"name": "Denner", "tier": 2},
    "migros": {"name": "Migros", "tier": 2},
    "coop": {"name": "Coop", "tier": 3},
    "lidl": {"name": "Lidl", "tier": 4},
}

# Rate limiting: minimum seconds between requests to the same domain.
# Conservative value since crawls run only once per week.
RATE_LIMIT_DELAY = 2.0
