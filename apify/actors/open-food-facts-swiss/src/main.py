"""
Swiss Open Food Facts Importer — Apify Actor
Fetches Swiss products from Open Food Facts API with nutritional data,
allergens, and Nutri-Score.
"""

import asyncio
import logging
import time

import httpx
from apify import Actor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

API_BASE = "https://world.openfoodfacts.org/api/v2/search"
API_FIELDS = (
    "code,product_name_de,brands,categories_tags_de,image_url,"
    "nutriments,nutriscore_grade,allergens_tags,quantity,stores_tags,"
    "completeness"
)
PAGE_SIZE = 100

# ---------------------------------------------------------------------------
# Allergen mapping: Open Food Facts tag -> simple name
# ---------------------------------------------------------------------------
ALLERGEN_MAP: dict[str, str] = {
    "en:milk": "lactose",
    "en:lactose": "lactose",
    "en:gluten": "gluten",
    "en:celery": "celery",
    "en:eggs": "eggs",
    "en:fish": "fish",
    "en:crustaceans": "crustaceans",
    "en:lupin": "lupin",
    "en:molluscs": "molluscs",
    "en:mustard": "mustard",
    "en:nuts": "nuts",
    "en:peanuts": "peanuts",
    "en:sesame-seeds": "sesame",
    "en:soybeans": "soy",
    "en:sulphur-dioxide-and-sulphites": "sulphites",
}

# ---------------------------------------------------------------------------
# Category mapping: keyword in OFF category -> our category
# ---------------------------------------------------------------------------
CATEGORY_KEYWORDS: list[tuple[str, str]] = [
    ("milch", "dairy"),
    ("käse", "dairy"),
    ("joghurt", "dairy"),
    ("butter", "dairy"),
    ("rahm", "dairy"),
    ("quark", "dairy"),
    ("molke", "dairy"),
    ("obst", "fruits"),
    ("frucht", "fruits"),
    ("früchte", "fruits"),
    ("apfel", "fruits"),
    ("beere", "fruits"),
    ("gemüse", "vegetables"),
    ("salat", "vegetables"),
    ("kartoffel", "vegetables"),
    ("tomate", "vegetables"),
    ("fleisch", "meat"),
    ("wurst", "meat"),
    ("schinken", "meat"),
    ("poulet", "meat"),
    ("rind", "meat"),
    ("schwein", "meat"),
    ("brot", "bakery"),
    ("gebäck", "bakery"),
    ("kuchen", "bakery"),
    ("gipfel", "bakery"),
    ("croissant", "bakery"),
    ("getränk", "beverages"),
    ("saft", "beverages"),
    ("wasser", "beverages"),
    ("bier", "beverages"),
    ("wein", "beverages"),
    ("kaffee", "beverages"),
    ("tee", "beverages"),
    ("limonade", "beverages"),
    ("schokolade", "sweets"),
    ("süss", "sweets"),
    ("bonbon", "sweets"),
    ("chips", "snacks"),
    ("snack", "snacks"),
    ("nüsse", "snacks"),
    ("nudel", "pasta"),
    ("pasta", "pasta"),
    ("reis", "grains"),
    ("mehl", "grains"),
    ("müesli", "grains"),
    ("cereal", "grains"),
    ("fisch", "seafood"),
    ("lachs", "seafood"),
    ("thunfisch", "seafood"),
    ("tiefkühl", "frozen"),
    ("eis", "frozen"),
    ("konserve", "canned"),
    ("dose", "canned"),
    ("sauce", "condiments"),
    ("senf", "condiments"),
    ("ketchup", "condiments"),
    ("öl", "condiments"),
    ("essig", "condiments"),
]


def _map_allergens(tags: list[str] | None) -> list[str]:
    """Map OFF allergen tags to simple allergen names, deduplicated."""
    if not tags:
        return []
    result: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        mapped = ALLERGEN_MAP.get(tag.lower().strip())
        if mapped and mapped not in seen:
            result.append(mapped)
            seen.add(mapped)
    return result


def _map_category(categories_de: list[str] | None) -> str | None:
    """Map OFF German category tags to our category using keyword matching."""
    if not categories_de:
        return None
    joined = " ".join(c.lower() for c in categories_de)
    for keyword, category in CATEGORY_KEYWORDS:
        if keyword in joined:
            return category
    return None


def _extract_nutritional_info(nutriments: dict | None) -> dict | None:
    """Extract calories, protein, fat, carbs from OFF nutriments dict."""
    if not nutriments:
        return None
    info: dict[str, float] = {}
    # OFF uses energy-kcal_100g or energy_100g (kJ)
    kcal = nutriments.get("energy-kcal_100g")
    if kcal is not None:
        info["calories"] = round(float(kcal), 1)
    protein = nutriments.get("proteins_100g")
    if protein is not None:
        info["protein"] = round(float(protein), 1)
    fat = nutriments.get("fat_100g")
    if fat is not None:
        info["fat"] = round(float(fat), 1)
    carbs = nutriments.get("carbohydrates_100g")
    if carbs is not None:
        info["carbs"] = round(float(carbs), 1)
    return info if info else None


def _transform_product(product: dict) -> dict | None:
    """Transform a raw OFF product into our output format. Returns None if invalid."""
    name = (product.get("product_name_de") or "").strip()
    if not name:
        return None

    completeness = product.get("completeness", 0)
    # completeness is 0..1 float in OFF API
    if completeness is None:
        completeness = 0

    ean = (product.get("code") or "").strip() or None
    brand = (product.get("brands") or "").strip() or None
    image_url = (product.get("image_url") or "").strip() or None
    nutriscore = (product.get("nutriscore_grade") or "").strip().upper() or None
    if nutriscore and nutriscore not in ("A", "B", "C", "D", "E"):
        nutriscore = None

    allergens = _map_allergens(product.get("allergens_tags"))
    category = _map_category(product.get("categories_tags_de"))
    nutritional_info = _extract_nutritional_info(product.get("nutriments"))

    stores_raw = product.get("stores_tags") or []
    stores = [s.strip().title() for s in stores_raw if s.strip()]

    return {
        "ean": ean,
        "name": name,
        "brand": brand,
        "price": None,
        "category": category,
        "image_url": image_url,
        "allergens": allergens,
        "nutritional_info": nutritional_info,
        "nutriscore": nutriscore,
        "stores": stores,
        "source": "openfoodfacts",
        "region": "switzerland",
        "completeness": completeness,
    }


async def main():
    async with Actor:
        actor_input = await Actor.get_input() or {}
        max_products = actor_input.get("maxProducts", 5000)
        categories = actor_input.get("categories") or []
        min_completeness = actor_input.get("minCompleteness", 50)
        # OFF API uses 0..1, input is 0..100
        min_completeness_ratio = min_completeness / 100.0

        logger.info(
            "Starting import: max=%d, categories=%s, minCompleteness=%d%%",
            max_products,
            categories or "all",
            min_completeness,
        )
        await Actor.set_status_message(
            f"Importing up to {max_products} Swiss products from Open Food Facts"
        )

        params: dict[str, str] = {
            "countries_tags_en": "Switzerland",
            "page_size": str(PAGE_SIZE),
            "fields": API_FIELDS,
            "sort_by": "unique_scans_n",
        }
        if categories:
            params["categories_tags"] = ",".join(categories)

        total_pushed = 0
        total_skipped = 0
        page = 1
        start_time = time.monotonic()

        async with httpx.AsyncClient(
            timeout=30.0,
            headers={"User-Agent": "korb.guru-bot/1.0 (contact@korb.guru)"},
        ) as http:
            while total_pushed < max_products:
                params["page"] = str(page)

                try:
                    resp = await http.get(API_BASE, params=params)
                    resp.raise_for_status()
                    data = resp.json()
                except httpx.HTTPStatusError as e:
                    logger.error("API error on page %d: %s", page, e)
                    break
                except Exception as e:
                    logger.error("Request failed on page %d: %s", page, e)
                    break

                products = data.get("products", [])
                if not products:
                    logger.info("No more products on page %d, stopping", page)
                    break

                for raw_product in products:
                    if total_pushed >= max_products:
                        break

                    transformed = _transform_product(raw_product)
                    if transformed is None:
                        total_skipped += 1
                        continue

                    if transformed["completeness"] < min_completeness_ratio:
                        total_skipped += 1
                        continue

                    # Remove completeness from output (internal filter only)
                    del transformed["completeness"]
                    await Actor.push_data(transformed)
                    total_pushed += 1

                logger.info(
                    "Page %d: pushed=%d, skipped=%d, total=%d/%d",
                    page,
                    len(products),
                    total_skipped,
                    total_pushed,
                    max_products,
                )

                # Check if we've reached the last page
                total_available = data.get("count", 0)
                if page * PAGE_SIZE >= total_available:
                    logger.info(
                        "Reached last page (%d products available)", total_available
                    )
                    break

                page += 1

                # Rate limit: 1 request per second
                await asyncio.sleep(1.0)

        elapsed = time.monotonic() - start_time
        finished_msg = (
            f"Done: {total_pushed} products imported, "
            f"{total_skipped} skipped, "
            f"{page} pages in {elapsed:.0f}s"
        )
        logger.info(finished_msg)

        kv_store = await Actor.open_key_value_store()
        await kv_store.set_value(
            "run-summary",
            {
                "total_imported": total_pushed,
                "total_skipped": total_skipped,
                "pages_fetched": page,
                "duration_s": round(elapsed, 1),
            },
        )

        await Actor.set_status_message(finished_msg)


if __name__ == "__main__":
    asyncio.run(main())
