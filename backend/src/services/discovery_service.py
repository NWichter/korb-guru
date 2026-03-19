"""Discovery Service — Qdrant Discovery API with Context Pairs.

Key differentiator for the Qdrant hackathon: uses swipe history to build
context pairs that progressively improve recommendation quality.
"""

import logging
import uuid

from qdrant_client import models
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.recipe import SwipeAction
from ..qdrant.client import get_qdrant_client
from .embedding_service import embed_text_async

logger = logging.getLogger(__name__)


async def get_context_pairs(
    user_id: str, session: AsyncSession, max_pairs: int = 10
) -> list[models.ContextPair]:
    """Build context pairs from swipe history (liked vs disliked recipes)."""
    accepts_result = await session.execute(
        select(SwipeAction)
        .where(
            SwipeAction.user_id == uuid.UUID(user_id),
            SwipeAction.action == "accept",
        )
        .order_by(SwipeAction.updated_at.desc())
    )
    accepts = accepts_result.scalars().all()

    rejects_result = await session.execute(
        select(SwipeAction)
        .where(
            SwipeAction.user_id == uuid.UUID(user_id),
            SwipeAction.action == "reject",
        )
        .order_by(SwipeAction.updated_at.desc())
    )
    rejects = rejects_result.scalars().all()

    if not accepts or not rejects:
        return []

    pairs = []
    for i, accept in enumerate(accepts[:max_pairs]):
        reject = rejects[i % len(rejects)]
        pairs.append(
            models.ContextPair(
                positive=str(accept.recipe_id),
                negative=str(reject.recipe_id),
            )
        )
    return pairs


def _household_filter(household_id: str | None) -> models.Filter | None:
    if not household_id:
        return None
    return models.Filter(
        should=[
            models.FieldCondition(
                key="household_id", match=models.MatchValue(value=household_id)
            ),
            models.IsNullCondition(is_null=models.PayloadField(key="household_id")),
        ]
    )


async def discover_with_context(
    user_id: str,
    session: AsyncSession,
    target_text: str | None = None,
    limit: int = 10,
    household_id: str | None = None,
) -> list:
    """Use Qdrant's Discovery API with accumulated context pairs."""
    try:
        client = get_qdrant_client()
        context_pairs = await get_context_pairs(user_id, session)
        query_filter = _household_filter(household_id)

        if target_text:
            target = await embed_text_async(target_text)
        else:
            pref_must = [
                models.FieldCondition(
                    key="user_id",
                    match=models.MatchValue(value=user_id),
                ),
                models.FieldCondition(
                    key="domain",
                    match=models.MatchValue(value="recipe"),
                ),
            ]
            if household_id:
                pref_must.append(
                    models.FieldCondition(
                        key="household_id",
                        match=models.MatchValue(value=household_id),
                    )
                )
            pref_results = client.scroll(
                collection_name="user_preferences",
                scroll_filter=models.Filter(must=pref_must),
                limit=1,
                with_vectors=True,
            )
            points = pref_results[0]
            if points:
                target = points[0].vector
                if isinstance(target, dict):
                    target = list(target.values())[0]
            else:
                target = await embed_text_async("healthy quick affordable meal")

        if context_pairs:
            logger.info(
                "Discovery search with %d context pairs for user %s",
                len(context_pairs),
                user_id,
            )
            # Use Qdrant's Discovery query with context pairs for re-ranking.
            # Discovery uses context pairs to adjust the target vector search,
            # which is more appropriate than RecommendQuery for this use case.
            results = client.query_points(
                collection_name="recipes",
                prefetch=models.Prefetch(
                    query=target,
                    limit=limit * 3,
                    filter=query_filter,
                ),
                query=models.DiscoverQuery(
                    discover=models.DiscoverInput(
                        target=target,
                        context=context_pairs,
                    ),
                ),
                query_filter=query_filter,
                limit=limit,
            ).points
        else:
            logger.info("Discovery fallback (no context pairs) for user %s", user_id)
            results = client.query_points(
                collection_name="recipes",
                query=target,
                query_filter=query_filter,
                limit=limit,
            ).points

        return results
    except Exception as e:
        logger.warning("Discovery search failed for user %s: %s", user_id, e)
        return []


async def get_discovery_metrics(user_id: str, session: AsyncSession) -> dict:
    """Track context improvement metrics for the demo."""
    client = get_qdrant_client()

    accepts_result = await session.execute(
        select(SwipeAction).where(
            SwipeAction.user_id == uuid.UUID(user_id),
            SwipeAction.action == "accept",
        )
    )
    accepts = accepts_result.scalars().all()

    rejects_result = await session.execute(
        select(SwipeAction).where(
            SwipeAction.user_id == uuid.UUID(user_id),
            SwipeAction.action == "reject",
        )
    )
    rejects = rejects_result.scalars().all()

    total_swipes = len(accepts) + len(rejects)
    context_pairs = await get_context_pairs(user_id, session)

    try:
        pref_results = client.scroll(
            collection_name="user_preferences",
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="user_id", match=models.MatchValue(value=user_id)
                    ),
                    models.FieldCondition(
                        key="domain", match=models.MatchValue(value="recipe")
                    ),
                ]
            ),
            limit=1,
        )
        has_preference_vector = len(pref_results[0]) > 0
    except Exception as e:
        logger.warning("Failed to check preference vector for user %s: %s", user_id, e)
        has_preference_vector = False

    if total_swipes == 0:
        phase = "cold_start"
        description = "No interactions yet. Using default recommendations."
    elif total_swipes < 5:
        phase = "learning"
        description = "Building initial preference profile. Recommendations improving."
    elif total_swipes < 15:
        phase = "personalized"
        description = (
            "Preference vector established. Discovery API active with context pairs."
        )
    else:
        phase = "refined"
        description = "Rich context history. Highly personalized recommendations."

    return {
        "user_id": user_id,
        "total_swipes": total_swipes,
        "total_accepts": len(accepts),
        "total_rejects": len(rejects),
        "context_pairs_available": len(context_pairs),
        "has_preference_vector": has_preference_vector,
        "phase": phase,
        "phase_description": description,
        "accept_rate": (
            round(len(accepts) / total_swipes * 100, 1) if total_swipes > 0 else 0
        ),
    }
