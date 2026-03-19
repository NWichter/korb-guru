"""
Shopping Agent — Apify Actor
Orchestrates grocery search, Qdrant retrieval, and LLM-powered recommendations.
"""

import asyncio
import hashlib
import json
import logging
from functools import lru_cache
from pathlib import Path

import httpx
from apify import Actor
from qdrant_client import QdrantClient, models

logger = logging.getLogger(__name__)

SPARSE_DIM = 2**20  # Must match crawler ingestion

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


@lru_cache(maxsize=None)
def _load_prompt(name: str) -> str:
    """Read a prompt markdown file from the prompts directory (cached)."""
    return (_PROMPTS_DIR / name).read_text(encoding="utf-8")


def _sparse_vector(text: str) -> tuple[list[int], list[float]]:
    """Build sparse BM25-style vector from tokenised text."""
    tokens = text.lower().split()
    seen: dict[int, int] = {}
    for token in tokens:
        h = int(hashlib.md5(token.encode()).hexdigest(), 16) % SPARSE_DIM
        seen[h] = seen.get(h, 0) + 1
    return list(seen.keys()), [float(v) for v in seen.values()]


def _get_qdrant_client(url: str | None, api_key: str | None) -> QdrantClient | None:
    """Connect to Qdrant Cloud if credentials provided."""
    if not url or not api_key:
        logger.warning("No Qdrant credentials — skipping vector search")
        return None
    try:
        client = QdrantClient(url=url, api_key=api_key, timeout=30)
        client.get_collections()  # verify connection
        return client
    except Exception as e:
        logger.error("Failed to connect to Qdrant: %s", e)
        return None


_embedding_model = None


def _get_embedding_model():
    """Lazy-load and cache the embedding model."""
    global _embedding_model
    if _embedding_model is None:
        from fastembed import TextEmbedding

        _embedding_model = TextEmbedding(
            model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        )
    return _embedding_model


def _embed_text(text: str) -> list[float]:
    """Embed text using fastembed (same model as crawler ingestion)."""
    model = _get_embedding_model()
    return list(model.embed([text]))[0].tolist()


def _search_qdrant(
    client: QdrantClient,
    query: str,
    retailers: list[str] | None = None,
    max_price: float | None = None,
    region: str | None = None,
    limit: int = 20,
) -> list[dict]:
    """Hybrid search on products collection."""
    dense_vector = _embed_text(query)
    sparse_indices, sparse_values = _sparse_vector(query)

    must_conditions = []
    if retailers:
        must_conditions.append(
            models.FieldCondition(key="retailer", match=models.MatchAny(any=retailers))
        )
    if max_price is not None:
        must_conditions.append(
            models.FieldCondition(key="price", range=models.Range(lte=max_price))
        )
    if region:
        must_conditions.append(
            models.FieldCondition(key="region", match=models.MatchValue(value=region))
        )

    query_filter = models.Filter(must=must_conditions) if must_conditions else None

    results = client.query_points(
        collection_name="products",
        prefetch=[
            models.Prefetch(
                query=models.SparseVector(indices=sparse_indices, values=sparse_values),
                using="sparse",
                limit=limit,
            ),
            models.Prefetch(query=dense_vector, using="dense", limit=limit),
        ],
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        query_filter=query_filter,
        limit=limit,
    )
    return [
        {
            "name": p.payload.get("name", ""),
            "price": p.payload.get("price"),
            "retailer": p.payload.get("retailer", ""),
            "category": p.payload.get("category", ""),
            "discount_pct": p.payload.get("discount_pct"),
            "score": p.score,
        }
        for p in results.points
    ]


async def _ask_llm(
    api_key: str, query: str, products: list[dict], budget: float
) -> str:
    """Ask OpenRouter LLM for shopping recommendations."""
    product_text = "\n".join(
        f"- {p['name']} ({p['retailer']}): CHF {p['price'] or '?'}"
        + (f" (-{p['discount_pct']:.0f}%)" if p.get("discount_pct") else "")
        for p in products
    )

    prompt_template = _load_prompt("shopping-recommendations.md")
    prompt = prompt_template.format(
        query=query, budget=f"{budget:.2f}", product_text=product_text
    )

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "google/gemini-2.5-flash",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 1500,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        choices = data.get("choices", [])
        if not choices:
            logger.warning("LLM returned no choices: %s", data)
            return "No recommendation could be generated."
        return choices[0].get("message", {}).get("content", "")


def _cache_key(query: str, budget: float, retailers: list[str] | None, region: str) -> str:
    """Build a deterministic cache key from query parameters.

    Includes today's date so cached results expire daily.
    """
    from datetime import date

    raw = json.dumps(
        {
            "q": query.lower().strip(),
            "b": budget,
            "r": sorted(retailers or []),
            "reg": region,
            "d": date.today().isoformat(),
        },
        sort_keys=True,
    )
    return f"cache-{hashlib.sha256(raw.encode()).hexdigest()[:16]}"


REGION_SEARCH_TERMS: dict[str, str] = {
    "zurich": "Zürich, Switzerland",
    "bern": "Bern, Switzerland",
    "basel": "Basel, Switzerland",
}

RETAILER_SEARCH_NAMES: dict[str, str] = {
    "aldi": "Aldi Suisse",
    "migros": "Migros",
    "coop": "Coop",
    "denner": "Denner",
    "lidl": "Lidl Schweiz",
}


async def _find_nearby_stores(retailers: list[str], region: str) -> list[dict]:
    """Call apify/google-maps-scraper to find nearby stores for given retailers."""
    from apify_client import ApifyClient

    location = REGION_SEARCH_TERMS.get(region, "Zürich, Switzerland")
    search_terms = [
        RETAILER_SEARCH_NAMES.get(r, r) for r in retailers
    ]

    apify_client = ApifyClient()
    stores: list[dict] = []

    try:
        run = apify_client.actor("apify/google-maps-scraper").call(
            run_input={
                "searchStringsArray": search_terms,
                "locationQuery": location,
                "maxCrawledPlacesPerSearch": 3,
                "language": "de",
                "maxImages": 0,
                "maxReviews": 0,
                "onlyDataFromSearchPage": False,
            },
            timeout_secs=120,
        )
        dataset_items = apify_client.dataset(run["defaultDatasetId"]).list_items().items
        for item in dataset_items:
            stores.append({
                "name": item.get("title", ""),
                "address": item.get("address", ""),
                "phone": item.get("phone", ""),
                "website": item.get("website", ""),
                "rating": item.get("totalScore"),
                "location": {
                    "lat": item.get("location", {}).get("lat"),
                    "lng": item.get("location", {}).get("lng"),
                },
                "opening_hours": item.get("openingHours"),
                "url": item.get("url", ""),
            })
    except Exception as e:
        logger.warning("Google Maps scraper failed: %s", e)

    return stores


async def main():
    async with Actor:
        actor_input = await Actor.get_input() or {}
        query = actor_input.get("query", "")
        budget = actor_input.get("budget", 50.0)
        retailers = actor_input.get("preferred_retailers")
        region = actor_input.get("region", "zurich")
        qdrant_url = actor_input.get("qdrant_url")
        qdrant_api_key = actor_input.get("qdrant_api_key")
        openrouter_key = actor_input.get("openrouter_api_key")
        scrape_fresh = actor_input.get("scrape_fresh", False)
        find_stores = actor_input.get("find_stores", False)

        if not query:
            logger.error("No query provided")
            await Actor.set_status_message("Error: no query provided")
            return

        await Actor.set_status_message(f"Processing: {query[:50]}...")
        logger.info("Query: %s | Budget: %.2f | Region: %s", query, budget, region)

        # Check KV store cache before doing any work
        cache_k = _cache_key(query, budget, retailers, region)
        cached = await Actor.get_value(cache_k)
        if cached is not None:
            logger.info("Cache hit for key %s", cache_k)
            await Actor.push_data(cached)
            await Actor.set_status_message("Done (cached result)")
            return

        # Step 1: Optionally run swiss-grocery-scraper for fresh data
        if scrape_fresh:
            await Actor.set_status_message("Running swiss-grocery-scraper for fresh data...")
            try:
                from apify_client import ApifyClient

                apify_client = ApifyClient()
                run = apify_client.actor("korb-guru/swiss-grocery-scraper").call(
                    run_input={
                        "retailers": retailers or ["aldi", "migros", "coop", "denner", "lidl"],
                        "region": region,
                        "maxItems": 100,
                    },
                    timeout_secs=300,
                )
                logger.info("Scraper run finished: %s", run.get("status"))
                logger.info(
                    "Note: scraped data needs ingestion before it appears in Qdrant. "
                    "If the scraper's webhook is configured, ingestion happens automatically."
                )
            except Exception as e:
                logger.warning("Fresh scrape failed (continuing with cached data): %s", e)

        # Step 2: Search Qdrant for matching products
        products = []
        qdrant_client = _get_qdrant_client(qdrant_url, qdrant_api_key)
        if qdrant_client:
            await Actor.set_status_message("Searching Qdrant for products...")
            products = _search_qdrant(
                qdrant_client,
                query,
                retailers=retailers,
                max_price=budget,
                region=region,
                limit=20,
            )
            logger.info("Found %d products via Qdrant", len(products))

        # Step 3: Generate LLM recommendation
        recommendation = ""
        if openrouter_key and products:
            await Actor.set_status_message("Generating AI recommendation...")
            try:
                recommendation = await _ask_llm(openrouter_key, query, products, budget)
                logger.info("LLM recommendation generated (%d chars)", len(recommendation))
            except Exception as e:
                logger.warning("LLM recommendation failed: %s", e)
                recommendation = "LLM-Empfehlung konnte nicht generiert werden."

        # Step 4: Optionally find nearby stores via Google Maps
        nearby_stores: list[dict] = []
        if find_stores:
            await Actor.set_status_message("Finding nearby stores via Google Maps...")
            search_retailers = retailers or ["aldi", "migros", "coop", "denner", "lidl"]
            # Only search for retailers that appear in the product results
            found_retailers = {p["retailer"] for p in products if p.get("retailer")}
            if found_retailers:
                search_retailers = [r for r in search_retailers if r in found_retailers]
            nearby_stores = await _find_nearby_stores(search_retailers, region)
            logger.info("Found %d nearby stores via Google Maps", len(nearby_stores))

        # Step 5: Calculate totals
        priced = [p for p in products if p.get("price")]
        total_cost = sum(p["price"] for p in priced)
        cheapest_per_item = {}
        for p in priced:
            name_key = p["name"].lower()
            if name_key not in cheapest_per_item or p["price"] < cheapest_per_item[name_key]["price"]:
                cheapest_per_item[name_key] = p

        result = {
            "query": query,
            "budget": budget,
            "region": region,
            "products_found": len(products),
            "total_cost": round(total_cost, 2),
            "within_budget": total_cost <= budget,
            "recommendation": recommendation,
            "products": products,
            "cheapest_options": list(cheapest_per_item.values()),
        }

        if nearby_stores:
            result["nearby_stores"] = nearby_stores

        await Actor.push_data(result)

        # Cache result in Actor's default key-value store
        await Actor.set_value(cache_k, result)

        # Also store latest result for easy retrieval
        kv_store = await Actor.open_key_value_store()
        await kv_store.set_value("shopping-result", result)

        msg = f"Done: {len(products)} products, CHF {total_cost:.2f}"
        if recommendation:
            msg += " + AI recommendation"
        if nearby_stores:
            msg += f" + {len(nearby_stores)} nearby stores"
        await Actor.set_status_message(msg)
        logger.info(msg)


if __name__ == "__main__":
    asyncio.run(main())
