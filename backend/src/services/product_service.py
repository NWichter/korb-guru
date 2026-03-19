"""Product service — hybrid search, comparison, deals via Qdrant."""

import hashlib
import logging
import re
import threading
import uuid

from qdrant_client import models

from ..qdrant.client import get_qdrant_client
from .embedding_service import embed_text

logger = logging.getLogger(__name__)


SPARSE_DIM = 2**20  # Must match crawler ingestion (SmartCart + Apify)


# ---------------------------------------------------------------------------
# Recommendation quality tracking (in-memory)
# ---------------------------------------------------------------------------


class _QualityTracker:
    """Thread-safe in-memory tracker for search and feedback metrics."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.search_count = 0
        self.feedback_count = 0
        self.positive_feedback = 0

    def record_search(self) -> None:
        with self._lock:
            self.search_count += 1

    def record_feedback(self, helpful: bool) -> None:
        with self._lock:
            self.feedback_count += 1
            if helpful:
                self.positive_feedback += 1

    @property
    def acceptance_rate(self) -> float:
        with self._lock:
            if self.feedback_count == 0:
                return 0.0
            return round(self.positive_feedback / self.feedback_count, 4)

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "search_count": self.search_count,
                "feedback_count": self.feedback_count,
                "acceptance_rate": self.acceptance_rate,
            }


quality_tracker = _QualityTracker()


def _sparse_vector(text: str) -> tuple[list[int], list[float]]:
    """Build sparse BM25-style vector from tokenised text."""
    tokens = text.lower().split()
    seen: dict[int, int] = {}
    for token in tokens:
        h = int(hashlib.md5(token.encode()).hexdigest(), 16) % SPARSE_DIM
        seen[h] = seen.get(h, 0) + 1
    return list(seen.keys()), [float(v) for v in seen.values()]


def _fetch_preference_vector(
    client, user_id: str, household_id: str | None = None
) -> list[float] | None:
    """Fetch the user's preference vector from user_preferences collection."""
    try:
        must = [
            models.FieldCondition(
                key="user_id", match=models.MatchValue(value=user_id)
            ),
            models.FieldCondition(
                key="domain", match=models.MatchValue(value="product")
            ),
        ]
        if household_id:
            must.append(
                models.FieldCondition(
                    key="household_id", match=models.MatchValue(value=household_id)
                )
            )
        results = client.scroll(
            collection_name="user_preferences",
            scroll_filter=models.Filter(must=must),
            with_vectors=True,
            limit=1,
        )[0]
        if results:
            vec = results[0].vector
            if isinstance(vec, dict):
                if not vec:
                    return None
                return list(vec.values())[0]
            return vec
    except Exception as e:
        logger.warning("Failed to fetch preference vector for user %s: %s", user_id, e)
    return None


def search_products_hybrid(
    query: str,
    retailers: list[str] | None = None,
    max_price: float | None = None,
    category: str | None = None,
    region: str | None = None,
    limit: int = 10,
    user_id: str | None = None,
    household_id: str | None = None,
    exclude_allergens: list[str] | None = None,
) -> list:
    quality_tracker.record_search()
    try:
        client = get_qdrant_client()
        dense_vector = embed_text(query)
        sparse_indices, sparse_values = _sparse_vector(query)

        must_conditions = []
        if retailers:
            must_conditions.append(
                models.FieldCondition(
                    key="retailer", match=models.MatchAny(any=retailers)
                )
            )
        if max_price is not None:
            must_conditions.append(
                models.FieldCondition(key="price", range=models.Range(lte=max_price))
            )
        if category:
            must_conditions.append(
                models.FieldCondition(
                    key="category", match=models.MatchValue(value=category)
                )
            )
        if region:
            must_conditions.append(
                models.FieldCondition(
                    key="region", match=models.MatchValue(value=region)
                )
            )

        must_not_conditions = []
        if exclude_allergens:
            for allergen in exclude_allergens:
                must_not_conditions.append(
                    models.FieldCondition(
                        key="allergens",
                        match=models.MatchText(text=allergen),
                    )
                )

        query_filter = None
        if must_conditions or must_not_conditions:
            query_filter = models.Filter(
                must=must_conditions or None,
                must_not=must_not_conditions or None,
            )

        prefetch_limit = max(20, limit)
        results = client.query_points(
            collection_name="products",
            prefetch=[
                models.Prefetch(
                    query=models.SparseVector(
                        indices=sparse_indices, values=sparse_values
                    ),
                    using="sparse",
                    limit=prefetch_limit,
                ),
                models.Prefetch(
                    query=dense_vector, using="dense", limit=prefetch_limit
                ),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            query_filter=query_filter,
            search_params=models.SearchParams(
                quantization=models.QuantizationSearchParams(
                    rescore=True,
                    oversampling=2.0,
                ),
            ),
            limit=limit,
        )
        points = results.points

        # Re-rank using user preference vector when user context is provided
        if user_id and points:
            pref_vec = _fetch_preference_vector(client, user_id, household_id)
            if pref_vec:
                points = _rerank_with_preference(points, pref_vec)

        return points
    except Exception as e:
        logger.error("Product search failed: %s", e)
        return []


def _rerank_with_preference(
    points: list, pref_vector: list[float], pref_weight: float = 0.3
) -> list:
    """Re-rank results blending original score with preference."""
    import math

    def _cosine_sim(a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0

    scored = []
    for p in points:
        vec = p.vector
        if isinstance(vec, dict):
            vec = vec.get("dense", [])
        if vec:
            pref_sim = _cosine_sim(vec, pref_vector)
        else:
            pref_sim = 0.0
        original = p.score if p.score is not None else 0.0
        blended = (1 - pref_weight) * original + pref_weight * pref_sim
        scored.append((blended, p))

    scored.sort(key=lambda x: x[0], reverse=True)
    for blended_score, p in scored:
        p.score = blended_score
    return [p for _, p in scored]


_COMPARE_RETAILERS = ["migros", "coop", "aldi", "denner", "lidl"]


def compare_products(query: str, limit: int = 30) -> dict:
    """Search for similar products across all retailers and group by normalized name.

    Uses Qdrant batch query API to search per-retailer in parallel for better
    performance than a single large search with post-filtering.

    Returns a dict with 'query' and 'comparisons' keys suitable for the API response.
    """
    try:
        client = get_qdrant_client()
        dense_vector = embed_text(query)
        sparse_indices, sparse_values = _sparse_vector(query)

        per_retailer_limit = max(10, limit // len(_COMPARE_RETAILERS))
        prefetch_limit = max(20, per_retailer_limit)

        def _make_prefetch() -> list[models.Prefetch]:
            return [
                models.Prefetch(
                    query=models.SparseVector(
                        indices=sparse_indices, values=sparse_values
                    ),
                    using="sparse",
                    limit=prefetch_limit,
                ),
                models.Prefetch(
                    query=dense_vector, using="dense", limit=prefetch_limit
                ),
            ]

        # One query per retailer + one unfiltered fallback
        batch_requests: list[models.QueryRequest] = []
        for retailer in _COMPARE_RETAILERS:
            batch_requests.append(
                models.QueryRequest(
                    prefetch=_make_prefetch(),
                    query=models.FusionQuery(fusion=models.Fusion.RRF),
                    filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="retailer",
                                match=models.MatchValue(value=retailer),
                            )
                        ]
                    ),
                    limit=per_retailer_limit,
                    with_payload=True,
                )
            )
        # Unfiltered query to catch retailers not in the explicit list
        batch_requests.append(
            models.QueryRequest(
                prefetch=_make_prefetch(),
                query=models.FusionQuery(fusion=models.Fusion.RRF),
                limit=per_retailer_limit,
                with_payload=True,
            )
        )

        batch_results = client.query_batch_points(
            collection_name="products",
            requests=batch_requests,
        )

        # Merge all results, deduplicate by point id
        seen_ids: set[str] = set()
        results: list = []
        for batch_result in batch_results:
            for point in batch_result.points:
                pid = str(point.id)
                if pid not in seen_ids:
                    seen_ids.add(pid)
                    results.append(point)

    except Exception as e:
        logger.error("Batch compare search failed: %s", e)
        results = []

    # Group by normalized product name using fuzzy matching
    groups: dict[str, list[dict]] = {}

    for r in results:
        payload = r.payload or {}
        name = payload.get("name", "")
        retailer = payload.get("retailer", "unknown")
        price = payload.get("price")

        if not name or price is None:
            continue

        norm = _normalize_for_grouping(name)
        # Find an existing group that matches
        matched_group = None
        for group_key in groups:
            if _fuzzy_match(norm, group_key):
                matched_group = group_key
                break

        if matched_group is None:
            matched_group = norm

        groups.setdefault(matched_group, []).append(
            {
                "retailer": retailer,
                "price": price,
                "name": name,
                "discount_pct": payload.get("discount_pct"),
                "id": str(r.id),
            }
        )

    # Build comparison response
    comparisons = []
    for _group_key, items in groups.items():
        # Deduplicate: keep cheapest per retailer
        by_retailer: dict[str, dict] = {}
        for item in items:
            ret = item["retailer"]
            if ret not in by_retailer or item["price"] < by_retailer[ret]["price"]:
                by_retailer[ret] = item

        retailers_sorted = sorted(by_retailer.values(), key=lambda x: x["price"])
        if len(retailers_sorted) < 1:
            continue

        cheapest_price = retailers_sorted[0]["price"]
        most_expensive = retailers_sorted[-1]["price"]
        savings_pct = (
            round((1 - cheapest_price / most_expensive) * 100, 1)
            if most_expensive > 0 and most_expensive != cheapest_price
            else 0.0
        )

        # Use the most common/shortest name as the group name
        group_name = min(
            (item["name"] for item in retailers_sorted),
            key=lambda n: len(n),
        )

        comparisons.append(
            {
                "product_name": group_name,
                "retailers": [
                    {
                        "retailer": item["retailer"],
                        "price": item["price"],
                        "name": item["name"],
                        "discount_pct": item.get("discount_pct"),
                    }
                    for item in retailers_sorted
                ],
                "cheapest": retailers_sorted[0]["retailer"],
                "savings_pct": savings_pct,
            }
        )

    # Sort groups: those with most retailers first, then by savings
    comparisons.sort(key=lambda c: (-len(c["retailers"]), -c["savings_pct"]))

    return {
        "query": query,
        "comparisons": comparisons[:limit],
    }


def _normalize_for_grouping(name: str) -> str:
    """Normalize product name for fuzzy grouping."""
    import unicodedata

    name = unicodedata.normalize("NFKC", name).lower().strip()
    _brand_re = (
        r"^(?:m-classic|m-budget|prix garantie|"
        r"naturaplan|qualité & prix|aha!|bio\s+)\s*"
    )
    name = re.sub(_brand_re, "", name)
    _unit_re = (
        r"\s*\d+\s*(?:x\s*\d+\s*)?"
        r"(?:g|kg|ml|l|cl|dl|stk|st|pcs?)\b"
    )
    name = re.sub(_unit_re, "", name)
    # Collapse whitespace
    name = " ".join(name.split())
    return name


def _fuzzy_match(a: str, b: str, threshold: float = 0.75) -> bool:
    """Simple token-based fuzzy matching for product name grouping."""
    if a == b:
        return True
    tokens_a = set(a.split())
    tokens_b = set(b.split())
    if not tokens_a or not tokens_b:
        return False
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    jaccard = len(intersection) / len(union)
    return jaccard >= threshold


def get_deals(limit: int = 20) -> list:
    try:
        client = get_qdrant_client()
        return client.scroll(
            collection_name="products",
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(key="discount_pct", range=models.Range(gt=0))
                ]
            ),
            limit=limit,
            order_by=models.OrderBy(
                key="discount_pct", direction=models.Direction.DESC
            ),
        )[0]
    except Exception as e:
        logger.warning("Get deals failed: %s", e)
        return []


def update_product_preference(
    user_id: str, product_id: str, helpful: bool, household_id: str | None = None
) -> None:
    """Update user preference vector based on product feedback (sync)."""
    quality_tracker.record_feedback(helpful)
    try:
        client = get_qdrant_client()

        # Fetch the product's dense vector from Qdrant
        points = client.retrieve(
            collection_name="products",
            ids=[product_id],
            with_vectors=["dense"],
        )
        if not points:
            logger.warning("Product %s not found for feedback", product_id)
            return

        product_vector = points[0].vector
        if isinstance(product_vector, dict):
            product_vector = product_vector["dense"]
    except Exception as e:
        logger.warning("Failed to fetch product %s for feedback: %s", product_id, e)
        return

    try:
        # Look up existing user preference vector
        pref_must = [
            models.FieldCondition(
                key="user_id", match=models.MatchValue(value=user_id)
            ),
            models.FieldCondition(
                key="domain", match=models.MatchValue(value="product")
            ),
        ]
        if household_id:
            pref_must.append(
                models.FieldCondition(
                    key="household_id", match=models.MatchValue(value=household_id)
                )
            )
        existing = client.query_points(
            collection_name="user_preferences",
            query_filter=models.Filter(must=pref_must),
            query=product_vector,
            with_vectors=True,
            limit=1,
        ).points

        if existing:
            point = existing[0]
            old_vector = point.vector
            if isinstance(old_vector, dict):
                old_vector = list(old_vector.values())[0]
            total = point.payload.get("total_accepts", 0) + point.payload.get(
                "total_rejects", 0
            )
            weight = 1.0 / (total + 1) if helpful else -0.5 / (total + 1)
            new_vector = [
                o + weight * (p - o) for o, p in zip(old_vector, product_vector)
            ]
            client.upsert(
                collection_name="user_preferences",
                points=[
                    models.PointStruct(
                        id=point.id,
                        vector=new_vector,
                        payload={
                            "user_id": user_id,
                            "household_id": household_id,
                            "domain": "product",
                            "total_accepts": point.payload.get("total_accepts", 0)
                            + (1 if helpful else 0),
                            "total_rejects": point.payload.get("total_rejects", 0)
                            + (0 if helpful else 1),
                        },
                    )
                ],
            )
        else:
            client.upsert(
                collection_name="user_preferences",
                points=[
                    models.PointStruct(
                        id=str(uuid.uuid4()),
                        vector=product_vector,
                        payload={
                            "user_id": user_id,
                            "household_id": household_id,
                            "domain": "product",
                            "total_accepts": 1 if helpful else 0,
                            "total_rejects": 0 if helpful else 1,
                        },
                    )
                ],
            )
    except Exception as e:
        logger.warning(
            "Failed to update product preference for user %s: %s", user_id, e
        )


def recommend_products(
    user_id: str,
    household_id: str | None = None,
    retailers: list[str] | None = None,
    limit: int = 10,
) -> list:
    """Recommend products using the user's preference vector via Qdrant recommend()."""
    try:
        client = get_qdrant_client()
        pref_vec = _fetch_preference_vector(client, user_id, household_id)
        if not pref_vec:
            logger.info("No preference vector for user %s, returning empty", user_id)
            return []

        must_conditions = []
        if retailers:
            must_conditions.append(
                models.FieldCondition(
                    key="retailer", match=models.MatchAny(any=retailers)
                )
            )
        query_filter = models.Filter(must=must_conditions) if must_conditions else None

        results = client.query_points(
            collection_name="products",
            query=pref_vec,
            using="dense",
            query_filter=query_filter,
            limit=limit,
        )
        return results.points
    except Exception as e:
        logger.warning("Product recommendations failed for user %s: %s", user_id, e)
        return []


def search_products_batch(
    queries: list[str],
    retailers: list[str] | None = None,
    max_price: float | None = None,
    limit: int = 10,
    user_id: str | None = None,
    household_id: str | None = None,
) -> dict[str, list]:
    """Run multiple product searches in a single Qdrant batch request."""
    try:
        client = get_qdrant_client()

        must_conditions = []
        if retailers:
            must_conditions.append(
                models.FieldCondition(
                    key="retailer", match=models.MatchAny(any=retailers)
                )
            )
        if max_price is not None:
            must_conditions.append(
                models.FieldCondition(key="price", range=models.Range(lte=max_price))
            )
        query_filter = models.Filter(must=must_conditions) if must_conditions else None

        prefetch_limit = max(20, limit)
        batch_requests = []
        for query in queries:
            dense_vector = embed_text(query)
            sparse_indices, sparse_values = _sparse_vector(query)
            batch_requests.append(
                models.QueryRequest(
                    prefetch=[
                        models.Prefetch(
                            query=models.SparseVector(
                                indices=sparse_indices, values=sparse_values
                            ),
                            using="sparse",
                            limit=prefetch_limit,
                        ),
                        models.Prefetch(
                            query=dense_vector, using="dense", limit=prefetch_limit
                        ),
                    ],
                    query=models.FusionQuery(fusion=models.Fusion.RRF),
                    filter=query_filter,
                    limit=limit,
                    with_payload=True,
                )
            )

        batch_results = client.query_batch_points(
            collection_name="products",
            requests=batch_requests,
        )

        result_map = {}
        pref_vec = None
        if user_id:
            pref_vec = _fetch_preference_vector(client, user_id, household_id)
        for query, result in zip(queries, batch_results):
            points = result.points
            if pref_vec and points:
                points = _rerank_with_preference(points, pref_vec)
            result_map[query] = points
        return result_map
    except Exception as e:
        logger.warning("Batch product search failed: %s", e)
        return {query: [] for query in queries}


def get_context_metrics() -> dict:
    """Gather Qdrant collection stats and quality tracking metrics."""
    try:
        client = get_qdrant_client()
    except Exception as e:
        logger.warning("Cannot connect to Qdrant for context metrics: %s", e)
        return {
            "total_products": 0,
            "total_recipes": 0,
            "total_preferences": 0,
            "retailers_covered": 0,
            "categories_covered": 0,
            **quality_tracker.snapshot(),
        }

    def _count_collection(name: str) -> int:
        try:
            info = client.get_collection(name)
            return info.points_count or 0
        except Exception:
            return 0

    total_products = _count_collection("products")
    total_recipes = _count_collection("recipes")
    total_preferences = _count_collection("user_preferences")

    # Count distinct retailers and categories via scroll sampling
    retailers: set[str] = set()
    categories: set[str] = set()
    try:
        offset = None
        while True:
            points, next_offset = client.scroll(
                collection_name="products",
                limit=200,
                offset=offset,
                with_payload=["retailer", "category"],
                with_vectors=False,
            )
            for p in points:
                payload = p.payload or {}
                r = payload.get("retailer")
                c = payload.get("category")
                if r:
                    retailers.add(r)
                if c:
                    categories.add(c)
            if next_offset is None:
                break
            offset = next_offset
    except Exception as e:
        logger.warning("Failed to scroll products for distinct counts: %s", e)

    return {
        "total_products": total_products,
        "total_recipes": total_recipes,
        "total_preferences": total_preferences,
        "retailers_covered": len(retailers),
        "categories_covered": len(categories),
        **quality_tracker.snapshot(),
    }


def get_context_improvement() -> dict:
    """Build a timeline showing how context quality improves over time.

    Reads real counts from Qdrant and derives the current stage.
    Public endpoint for demo / judges.
    """
    products_count = 0
    recipes_count = 0
    preferences_count = 0
    products_indexed_fields: list[str] = []

    try:
        client = get_qdrant_client()
    except Exception as e:
        logger.warning("Cannot connect to Qdrant for context improvement: %s", e)
        client = None

    def _count(name: str) -> int:
        if client is None:
            return 0
        try:
            info = client.get_collection(name)
            return info.points_count or 0
        except Exception:
            return 0

    products_count = _count("products")
    recipes_count = _count("recipes")
    preferences_count = _count("user_preferences")

    # Fetch indexed payload fields for products collection
    if client is not None:
        try:
            info = client.get_collection("products")
            if info.payload_schema:
                products_indexed_fields = sorted(info.payload_schema.keys())
        except Exception:
            pass

    # Determine current stage
    if products_count == 0:
        current_stage = "cold_start"
    elif preferences_count > 50:
        current_stage = "proactive"
    elif preferences_count > 0:
        current_stage = "personalized"
    else:
        current_stage = "data_ingested"

    timeline = [
        {
            "stage": "cold_start",
            "label": "Woche 1 — Kaltstart",
            "products": 0,
            "recipes": 0,
            "preferences": 0,
            "search_quality": "generic",
            "description": "Keine Daten, keine Personalisierung",
        },
        {
            "stage": "data_ingested",
            "label": "Woche 2 — Daten geladen",
            "products": products_count,
            "recipes": recipes_count,
            "preferences": 0,
            "search_quality": "semantic",
            "description": "Hybrid Search aktiv, noch keine Personalisierung",
        },
        {
            "stage": "personalized",
            "label": "Woche 4 — Personalisiert",
            "products": products_count,
            "recipes": recipes_count,
            "preferences": preferences_count,
            "search_quality": "personalized",
            "description": ("Empfehlungen basieren auf Swipe-History und Feedback"),
        },
        {
            "stage": "proactive",
            "label": "Woche 8 — Proaktiv",
            "products": products_count,
            "recipes": recipes_count,
            "preferences": preferences_count,
            "search_quality": "proactive",
            "description": (
                "System schlägt proaktiv Mahlzeiten vor basierend auf "
                "Saison, Budget und Vorlieben"
            ),
        },
    ]

    return {
        "timeline": timeline,
        "current_stage": current_stage,
        "features_used": [
            "hybrid_search_rrf",
            "discovery_api",
            "named_vectors",
            "payload_filtering",
            "int8_quantization",
            "user_preference_learning",
            "domain_partitioning",
        ],
        "collections": {
            "products": {
                "points": products_count,
                "indexed_fields": products_indexed_fields,
            },
            "recipes": {"points": recipes_count},
            "user_preferences": {"points": preferences_count},
        },
    }
