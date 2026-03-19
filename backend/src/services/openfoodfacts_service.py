"""Open Food Facts import service — fetches Swiss products and maps them."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import random
import uuid
from typing import Any

import httpx

logger = logging.getLogger(__name__)

OFF_BASE_URL = "https://world.openfoodfacts.org/api/v2/search"
OFF_FIELDS = (
    "code,product_name_de,brands,categories_tags_de,image_front_small_url,"
    "nutriments,nutriscore_grade,allergens_tags,quantity,stores_tags"
)

ALLERGEN_MAP: dict[str, str] = {
    "en:milk": "milk",
    "en:gluten": "gluten",
    "en:nuts": "nuts",
    "en:eggs": "eggs",
    "en:soybeans": "soy",
    "en:fish": "fish",
    "en:celery": "celery",
    "en:mustard": "mustard",
    "en:sesame-seeds": "sesame",
    "en:peanuts": "peanuts",
}

# Keyword → category mapping (checked against categories_tags_de)
CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "dairy": [
        "milch",
        "joghurt",
        "käse",
        "butter",
        "rahm",
        "quark",
        "kefir",
        "mozzarella",
        "emmentaler",
        "gruyère",
        "ricotta",
        "mascarpone",
        "fromage",
        "yogurt",
        "cream",
        "cheese",
        "lait",
    ],
    "fruits": [
        "frucht",
        "früchte",
        "obst",
        "apfel",
        "birne",
        "banane",
        "orange",
        "zitrone",
        "beere",
        "kiwi",
        "mango",
        "ananas",
        "traube",
        "fruit",
    ],
    "vegetables": [
        "gemüse",
        "salat",
        "tomate",
        "karotte",
        "zwiebel",
        "kartoffel",
        "gurke",
        "paprika",
        "brokkoli",
        "spinat",
        "légume",
        "vegetable",
    ],
    "meat": [
        "fleisch",
        "poulet",
        "rind",
        "schwein",
        "huhn",
        "wurst",
        "schinken",
        "salami",
        "hack",
        "steak",
        "viande",
        "meat",
        "chicken",
        "beef",
        "pork",
    ],
    "bakery": [
        "brot",
        "brötchen",
        "gipfeli",
        "croissant",
        "kuchen",
        "torte",
        "zopf",
        "baguette",
        "toast",
        "pain",
        "bread",
        "bakery",
    ],
    "beverages": [
        "getränk",
        "wasser",
        "saft",
        "limonade",
        "cola",
        "eistee",
        "sirup",
        "drink",
        "juice",
        "boisson",
        "eau",
        "beverage",
    ],
    "snacks": [
        "chips",
        "snack",
        "cracker",
        "nüssli",
        "riegel",
        "keks",
        "biscuit",
        "pretzel",
        "bretzel",
        "popcorn",
    ],
    "frozen": [
        "tiefkühl",
        "gefroren",
        "glacé",
        "glace",
        "eis",
        "pizza",
        "surgelé",
        "frozen",
        "ice cream",
    ],
    "pasta_rice": [
        "pasta",
        "nudel",
        "spaghetti",
        "penne",
        "reis",
        "risotto",
        "couscous",
        "noodle",
        "riz",
        "pâtes",
    ],
    "canned": [
        "konserve",
        "dose",
        "büchse",
        "conserve",
        "canned",
        "thon",
        "thunfisch",
    ],
    "sauces": [
        "sauce",
        "ketchup",
        "senf",
        "mayonnaise",
        "dressing",
        "pesto",
        "sosse",
        "soße",
    ],
    "breakfast": [
        "müesli",
        "müsli",
        "cornflakes",
        "flocken",
        "cerealien",
        "cereal",
        "granola",
        "porridge",
        "haferflocken",
    ],
    "sweets": [
        "schokolade",
        "praline",
        "bonbon",
        "gummibär",
        "konfitüre",
        "marmelade",
        "honig",
        "chocolat",
        "chocolate",
        "candy",
        "süssigkeit",
    ],
    "hygiene": [
        "shampoo",
        "seife",
        "zahnpasta",
        "deodorant",
        "duschgel",
        "hygiene",
        "körperpflege",
        "soap",
        "toothpaste",
    ],
    "cleaning": [
        "reiniger",
        "waschmittel",
        "spülmittel",
        "putzmittel",
        "cleaning",
        "detergent",
        "nettoyant",
    ],
    "baby": [
        "baby",
        "säugling",
        "windel",
        "bébé",
    ],
    "pet": [
        "tierfutter",
        "katzenfutter",
        "hundefutter",
        "pet food",
    ],
    "alcohol": [
        "bier",
        "wein",
        "schnaps",
        "whisky",
        "vodka",
        "gin",
        "rum",
        "prosecco",
        "champagner",
        "beer",
        "wine",
        "alcool",
    ],
    "spices": [
        "gewürz",
        "salz",
        "pfeffer",
        "curry",
        "paprika",
        "zimt",
        "épice",
        "spice",
        "herb",
        "kräuter",
    ],
    "organic": [
        "bio",
        "organic",
        "biologique",
    ],
    "coffee_tea": [
        "kaffee",
        "tee",
        "espresso",
        "cappuccino",
        "café",
        "coffee",
        "tea",
        "thé",
    ],
    "oils_vinegar": [
        "öl",
        "essig",
        "olivenöl",
        "rapsöl",
        "sonnenblumenöl",
        "huile",
        "vinaigre",
        "oil",
        "vinegar",
    ],
    "nuts_seeds": [
        "nuss",
        "nüsse",
        "mandel",
        "cashew",
        "samen",
        "kerne",
        "noix",
        "nut",
        "seed",
        "amande",
    ],
    "ready_meals": [
        "fertiggericht",
        "convenience",
        "ready meal",
        "plat préparé",
        "menü",
        "mahlzeit",
    ],
}

RETAILER_KEYWORDS = ["migros", "coop", "aldi", "denner", "lidl"]


def _deterministic_uuid(code: str) -> uuid.UUID:
    """Generate a deterministic UUID from an OFF barcode."""
    return uuid.UUID(hashlib.md5(f"off:{code}".encode()).hexdigest())


def _map_allergens(allergens_tags: list[str]) -> list[str]:
    """Map OFF allergen tags to simple names."""
    mapped: list[str] = []
    for tag in allergens_tags:
        simple = ALLERGEN_MAP.get(tag)
        if simple and simple not in mapped:
            mapped.append(simple)
    return mapped


def _map_category(categories_tags_de: list[str]) -> str | None:
    """Map OFF category tags to our internal categories by keyword matching."""
    combined = " ".join(tag.lower() for tag in categories_tags_de)
    for category, keywords in CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if keyword in combined:
                return category
    return None


# CHF price ranges per category (min, max)
PRICE_RANGES: dict[str, tuple[float, float]] = {
    "dairy": (1.20, 8.50),
    "fruits": (1.50, 5.90),
    "vegetables": (0.90, 4.50),
    "meat": (4.50, 25.00),
    "bakery": (1.20, 6.50),
    "beverages": (0.80, 4.50),
    "snacks": (1.50, 6.90),
    "frozen": (2.50, 12.00),
    "pasta_rice": (1.20, 4.90),
    "canned": (1.50, 5.50),
    "sauces": (2.00, 7.50),
    "breakfast": (2.50, 8.90),
    "sweets": (1.80, 6.90),
    "hygiene": (2.00, 9.90),
    "cleaning": (2.50, 12.00),
    "baby": (3.50, 15.00),
    "pet": (2.00, 12.00),
    "alcohol": (2.50, 25.00),
    "spices": (1.50, 6.50),
    "organic": (2.50, 12.00),
    "coffee_tea": (3.50, 12.00),
    "oils_vinegar": (3.00, 12.00),
    "nuts_seeds": (3.00, 9.00),
    "ready_meals": (4.50, 12.00),
    "baby_food": (1.50, 6.00),
}


def _estimate_price(category: str | None, name: str, quantity: str) -> float:
    """Estimate a realistic CHF price based on category and quantity."""
    lo, hi = PRICE_RANGES.get(category or "", (1.50, 8.00))

    # Adjust by quantity keywords
    name_lower = name.lower() + " " + quantity.lower()
    if any(w in name_lower for w in ("1kg", "1000g", "1l", "1000ml")):
        lo, hi = lo * 1.2, hi * 1.2
    elif any(w in name_lower for w in ("500g", "500ml", "0.5l")):
        lo, hi = lo * 0.8, hi * 0.9
    elif any(w in name_lower for w in ("250g", "250ml", "0.25l")):
        lo, hi = lo * 0.5, hi * 0.6
    elif any(w in name_lower for w in ("2kg", "2l", "2000")):
        lo, hi = lo * 1.8, hi * 1.8

    # Bio/organic premium
    if "bio" in name_lower or "organic" in name_lower:
        lo, hi = lo * 1.3, hi * 1.3

    # Deterministic but varied price based on product name hash
    seed = int(hashlib.md5(name.encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)
    price = round(rng.uniform(lo, hi), 2)

    # Swiss-style rounding (0.05 increments)
    return round(round(price * 20) / 20, 2)


def _detect_retailer(stores_tags: list[str] | None, brands: str | None) -> str:
    """Detect retailer from stores_tags or brand name."""
    search_text = ""
    if stores_tags:
        search_text += " ".join(stores_tags).lower()
    if brands:
        search_text += " " + brands.lower()

    for retailer in RETAILER_KEYWORDS:
        if retailer in search_text:
            return retailer
    return "other"


def _extract_nutritional_info(nutriments: dict[str, Any]) -> str | None:
    """Extract nutritional info as JSON string."""
    info: dict[str, float | None] = {
        "energy_kcal_100g": nutriments.get("energy-kcal_100g"),
        "proteins_100g": nutriments.get("proteins_100g"),
        "fat_100g": nutriments.get("fat_100g"),
        "carbohydrates_100g": nutriments.get("carbohydrates_100g"),
    }
    if all(v is None for v in info.values()):
        return None
    return json.dumps(info)


def _map_product(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Map a single OFF product to our Product dict. Returns None if unusable."""
    name = raw.get("product_name_de")
    code = raw.get("code")
    if not name or not code:
        return None

    allergens_tags = raw.get("allergens_tags") or []
    categories_tags = raw.get("categories_tags_de") or []
    nutriments = raw.get("nutriments") or {}
    stores_tags = raw.get("stores_tags") or []
    brands = raw.get("brands")

    allergens = _map_allergens(allergens_tags)
    category = _map_category(categories_tags)
    retailer = _detect_retailer(stores_tags, brands)
    nutritional_info = _extract_nutritional_info(nutriments)

    price = _estimate_price(category, name.strip(), raw.get("quantity") or "")

    return {
        "id": _deterministic_uuid(code),
        "ean": code,
        "retailer": retailer,
        "name": name.strip(),
        "description": f"{brands or ''} {raw.get('quantity', '')}".strip() or None,
        "price": price,
        "original_price": None,
        "discount_pct": None,
        "category": category,
        "image_url": raw.get("image_front_small_url"),
        "allergens": ",".join(allergens) if allergens else None,
        "nutriscore": raw.get("nutriscore_grade"),
        "nutritional_info": nutritional_info,
        "source": "openfoodfacts",
    }


async def fetch_swiss_products(max_products: int = 100_000) -> list[dict[str, Any]]:
    """Fetch Swiss products from Open Food Facts, paginating through all pages.

    Rate-limited to 1 request/second as requested by OFF.
    """
    products: list[dict[str, Any]] = []
    page = 1
    page_size = 100

    async with httpx.AsyncClient(timeout=30.0) as client:
        while len(products) < max_products:
            params = {
                "countries_tags_en": "Switzerland",
                "page_size": page_size,
                "page": page,
                "fields": OFF_FIELDS,
                "sort_by": "unique_scans_n",
            }

            try:
                resp = await client.get(OFF_BASE_URL, params=params)
                resp.raise_for_status()
                data = resp.json()
            except Exception:
                logger.exception("Failed to fetch OFF page %d, skipping", page)
                page += 1
                await asyncio.sleep(1)
                continue

            raw_products = data.get("products", [])
            if not raw_products:
                logger.info("No more products on page %d, stopping", page)
                break

            for raw in raw_products:
                mapped = _map_product(raw)
                if mapped:
                    products.append(mapped)
                    if len(products) >= max_products:
                        break

            logger.info(
                "OFF page %d: fetched %d raw, %d mapped total",
                page,
                len(raw_products),
                len(products),
            )

            if len(products) % 1000 < page_size:
                logger.info("Progress: %d products fetched so far", len(products))

            page += 1
            # Rate limit: 1 req/sec as OFF asks
            await asyncio.sleep(1)

    logger.info("Open Food Facts import complete: %d products total", len(products))
    return products


async def enrich_prices_llm(
    products: list[dict[str, Any]],
    max_enriched: int = 1000,
    apify_token: str | None = None,
    openrouter_key: str | None = None,
) -> int:
    """Enrich top-N products with LLM-estimated prices.

    Uses Apify OpenRouter proxy (free) or direct OpenRouter.
    Products are sorted by popularity (OFF sorts by scans).
    Only the first `max_enriched` get LLM prices; rest keep
    rule-based estimates.
    """
    if not apify_token and not openrouter_key:
        logger.info("No LLM keys, skipping price enrichment")
        return 0

    url = (
        "https://openrouter.apify.actor/api/v1/chat/completions"
        if apify_token
        else "https://openrouter.ai/api/v1/chat/completions"
    )
    headers = {
        "Authorization": f"Bearer {apify_token or openrouter_key}",
        "Content-Type": "application/json",
    }

    enriched = 0
    batch_size = 20  # 20 products per LLM call

    async with httpx.AsyncClient(timeout=30.0) as client:
        for i in range(0, min(len(products), max_enriched), batch_size):
            batch = products[i : i + batch_size]
            names = [f"{p['name']} ({p.get('category', '?')})" for p in batch]
            prompt = (
                "Schätze realistische Schweizer Detailhandelspreise "
                "(CHF) für diese Produkte. Antworte NUR mit einer "
                "JSON-Liste von Zahlen, z.B. [2.95, 4.50, ...].\n\n"
                + "\n".join(f"{j + 1}. {n}" for j, n in enumerate(names))
            )

            try:
                resp = await client.post(
                    url,
                    headers=headers,
                    json={
                        "model": "google/gemini-2.0-flash-exp:free",
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.3,
                    },
                )
                text = resp.json()["choices"][0]["message"]["content"]
                # Parse JSON array from response
                import re as _re

                match = _re.search(r"\[[\d.,\s]+\]", text)
                if match:
                    prices = json.loads(match.group())
                    for p, price in zip(batch, prices):
                        if isinstance(price, (int, float)) and price > 0:
                            p["price"] = round(round(float(price) * 20) / 20, 2)
                            enriched += 1
            except Exception:
                logger.warning("LLM batch %d failed, keeping estimates", i)

            if enriched % 100 == 0 and enriched > 0:
                logger.info("LLM enriched %d/%d prices", enriched, max_enriched)
            await asyncio.sleep(0.5)

    logger.info("LLM price enrichment: %d products updated", enriched)
    return enriched
