# Qdrant Integration

Qdrant is the intelligence layer of korb.guru — not just vector storage, but the engine for self-improving recommendations. We use **Qdrant Cloud** with 3 collections that power hybrid search, recipe discovery, and evolving user preferences.

## Collections

### 1. `products` — Hybrid Search

| Property        | Value                                                                                  |
| --------------- | -------------------------------------------------------------------------------------- |
| Dense vectors   | `paraphrase-multilingual-MiniLM-L12-v2` (384 dims, COSINE)                             |
| Sparse vectors  | BM25 with IDF modifier (2^20 = 1,048,576 buckets)                                      |
| Quantization    | Scalar INT8 (quantile=0.99, always_ram=True) with oversampling + rescore               |
| Payload indexes | KEYWORD (retailer, category, region), FLOAT (price, discount_pct), DATETIME (valid_to) |

**Search method:** Reciprocal Rank Fusion (RRF) merges dense and sparse prefetch results. Preference-based re-ranking blends hybrid scores with user taste similarity.

**Fed by:** Apify swiss-grocery-scraper (weekly), Open Food Facts import (102k+ products), SmartCart crawlers.

### 2. `recipes` — Semantic Search + Discovery

| Property        | Value                                  |
| --------------- | -------------------------------------- |
| Dense vectors   | 384 dims, COSINE                       |
| Payload indexes | type, cost, time_minutes, household_id |

**Search method:** Recommend API uses positive (liked) and negative (disliked) recipe examples from swipe history.

**Fed by:** recipe-collector Actor, API recipe creation, seeded data (3,500+ recipes).

### 3. `user_preferences` — Evolving Taste Vectors

| Property      | Value                                                 |
| ------------- | ----------------------------------------------------- |
| Dense vectors | 384 dims                                              |
| Payload       | user_id, domain ("recipe" \| "product"), household_id |

**Update method:** Exponential Moving Average (EMA) — every swipe action updates the preference vector. Early interactions have strong influence (cold-start bootstrap), later interactions make finer adjustments.

## Qdrant Features Used

| Feature                        | Where                                       | Purpose                                               |
| ------------------------------ | ------------------------------------------- | ----------------------------------------------------- |
| Named vectors (dense + sparse) | `backend/src/qdrant/collections.py`         | Single point stores both semantic and keyword vectors |
| Reciprocal Rank Fusion         | `backend/src/services/product_service.py`   | Merges dense and sparse prefetch results              |
| Recommend API                  | `backend/src/services/recipe_service.py`    | Recipe suggestions from liked/disliked swipe history  |
| Discovery API + context pairs  | `backend/src/services/discovery_service.py` | Progressively refined search regions from swipes      |
| Payload filtering              | `backend/src/services/product_service.py`   | Retailer, price, category, region, expiration filters |
| Scalar quantization (INT8)     | `backend/src/qdrant/collections.py`         | Reduced memory with oversampling + rescore            |
| IDF modifier on sparse vectors | `backend/src/qdrant/collections.py`         | Better BM25 relevance scoring                         |
| Multi-mode client              | `backend/src/qdrant/client.py`              | cloud / docker / local / memory deployment            |
| query_batch_points             | `backend/src/services/product_service.py`   | Batch hybrid search for ingredient lists (up to 20)   |
| Preference-based re-ranking    | `backend/src/services/product_service.py`   | Blends hybrid scores with user preference similarity  |
| Scroll API                     | `backend/src/services/`                     | Batch operations and data export                      |

## Self-Improving Context — The Core Story

This directly answers the Qdrant challenge question: _"demonstrate how that context can be improved."_

### Three Axes of Improvement

1. **User-driven** — Swipes → EMA → preference vectors → better recommendations
2. **Data-driven** — Weekly scraping adds ~370 new products, expanding what Qdrant can find
3. **Interaction-driven** — Discovery API context pairs accumulate, creating increasingly precise search regions

### Progressive Personalization

```
Cold Start (0 swipes):
  → Generic results, no personalization
  → Recommend API returns popular recipes

Bootstrap Phase (1-4 swipes):
  → EMA updates have strong influence (high learning rate)
  → Preference vector quickly aligns to user taste

Discovery Phase (5+ swipes):
  → Discovery API activates with context pairs
  → Pairs define "near recipes like this, far from recipes like that"
  → Up to 10 context pairs per user
  → Recommendations become highly personalized

Ongoing Refinement:
  → Later swipes make finer adjustments (lower EMA weight)
  → Weekly new products expand the search space
  → Preference-based re-ranking blends hybrid scores with taste similarity
```

## Backend Services Using Qdrant

| Service          | File                                        | Key Methods                                                       |
| ---------------- | ------------------------------------------- | ----------------------------------------------------------------- |
| ProductService   | `backend/src/services/product_service.py`   | `search()`, `compare_products()`, `get_deals()`, `batch_search()` |
| RecipeService    | `backend/src/services/recipe_service.py`    | `search()`, `recommend()`, `swipe()`, `update_preferences()`      |
| DiscoveryService | `backend/src/services/discovery_service.py` | `discover()`, `get_context_pairs()`, `discovery_metrics()`        |
| EmbeddingService | `backend/src/services/embedding_service.py` | `embed()`, `embed_batch()`                                        |

## Seed Scripts

`scripts/seed-qdrant.mjs` — Seeds all 3 collections with initial data for development and demo purposes.

## Deployment

- **Production:** Qdrant Cloud (`QDRANT_MODE=cloud`, `QDRANT_URL`, `QDRANT_API_KEY`)
- **Local dev:** `docker compose -f docker-compose.infra.yml --env-file .env.infra up -d`
- **Tests:** In-memory mode (`QDRANT_MODE=memory`)
