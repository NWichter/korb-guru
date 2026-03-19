"""Apify crawler configuration."""
import os

APIFY_TOKEN = os.getenv("APIFY_TOKEN", "")

# Custom Actor handles all 5 Swiss retailers
CUSTOM_ACTOR_ID = "korb-guru/swiss-grocery-scraper"

ALL_RETAILERS = ["aldi", "migros", "coop", "denner", "lidl"]

CUSTOM_ACTOR_INPUT = {
    "retailers": ALL_RETAILERS,
    "region": "zurich",
    "maxItems": 200,
}

# Retry configuration
MAX_RETRIES = 2
ACTOR_TIMEOUT_SECS = 600

# Qdrant config (from env)
QDRANT_MODE = os.getenv("QDRANT_MODE", "docker")
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
