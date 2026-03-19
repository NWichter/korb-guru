"""Recipe service — Qdrant embeddings, semantic search, recommendations."""

import logging
import uuid

from qdrant_client import models
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.recipe import SwipeAction
from ..qdrant.client import get_qdrant_client
from .embedding_service import embed_text

logger = logging.getLogger(__name__)


def upsert_recipe_embedding(recipe, ingredients: list) -> None:
    """Embed recipe and upsert to Qdrant. Runs sync (Qdrant client is sync)."""
    try:
        client = get_qdrant_client()
        text = (
            f"{recipe.title} {recipe.description or ''} "
            f"{' '.join(i.name for i in ingredients)}"
        )
        vector = embed_text(text)
        client.upsert(
            collection_name="recipes",
            points=[
                models.PointStruct(
                    id=str(recipe.id),
                    vector=vector,
                    payload={
                        "recipe_id": str(recipe.id),
                        "type": recipe.type,
                        "cost": float(recipe.cost),
                        "time_minutes": recipe.time_minutes,
                        "household_id": (
                            str(recipe.household_id) if recipe.household_id else None
                        ),
                    },
                )
            ],
        )
    except Exception as e:
        logger.warning("Failed to upsert recipe embedding for %s: %s", recipe.id, e)


def search_recipes_semantic(
    query: str, household_id: str | None = None, limit: int = 10
) -> list:
    try:
        client = get_qdrant_client()
        vector = embed_text(query)
        query_filter = None
        if household_id:
            query_filter = models.Filter(
                should=[
                    models.FieldCondition(
                        key="household_id",
                        match=models.MatchValue(value=household_id),
                    ),
                    models.IsNullCondition(
                        is_null=models.PayloadField(key="household_id")
                    ),
                ]
            )
        return client.query_points(
            collection_name="recipes",
            query=vector,
            query_filter=query_filter,
            limit=limit,
        ).points
    except Exception as e:
        logger.warning("Recipe search failed: %s", e)
        return []


async def get_recommendations(
    user_id: str,
    session: AsyncSession,
    limit: int = 10,
    household_id: str | None = None,
) -> list:
    try:
        client = get_qdrant_client()

        accepts_result = await session.execute(
            select(SwipeAction)
            .where(
                SwipeAction.user_id == uuid.UUID(user_id),
                SwipeAction.action == "accept",
            )
            .order_by(SwipeAction.created_at.desc())
            .limit(5)
        )
        accepts = accepts_result.scalars().all()

        rejects_result = await session.execute(
            select(SwipeAction)
            .where(
                SwipeAction.user_id == uuid.UUID(user_id),
                SwipeAction.action == "reject",
            )
            .order_by(SwipeAction.created_at.desc())
            .limit(3)
        )
        rejects = rejects_result.scalars().all()

        query_filter = None
        if household_id:
            query_filter = models.Filter(
                should=[
                    models.FieldCondition(
                        key="household_id",
                        match=models.MatchValue(value=household_id),
                    ),
                    models.IsNullCondition(
                        is_null=models.PayloadField(key="household_id")
                    ),
                ]
            )

        if not accepts:
            return client.query_points(
                collection_name="recipes",
                query=embed_text("healthy meal"),
                query_filter=query_filter,
                limit=limit,
            ).points

        positive_ids = [str(a.recipe_id) for a in accepts]
        negative_ids = [str(r.recipe_id) for r in rejects]

        return client.query_points(
            collection_name="recipes",
            query=models.RecommendQuery(
                recommend=models.RecommendInput(
                    positive=positive_ids,
                    negative=negative_ids if negative_ids else None,
                ),
            ),
            query_filter=query_filter,
            limit=limit,
        ).points
    except Exception as e:
        logger.warning("Recommendations failed for user %s: %s", user_id, e)
        return []


def update_user_preference(
    user_id: str, recipe, action: str, household_id: str | None = None
) -> None:
    """Update user preference vector in Qdrant (sync)."""
    try:
        client = get_qdrant_client()
        text = f"{recipe.title} {recipe.description or ''}"
        recipe_vector = embed_text(text)

        existing = client.query_points(
            collection_name="user_preferences",
            query_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="user_id", match=models.MatchValue(value=user_id)
                    ),
                    models.FieldCondition(
                        key="domain", match=models.MatchValue(value="recipe")
                    ),
                ]
            ),
            query=recipe_vector,
            with_vectors=True,
            limit=1,
        ).points
    except Exception as e:
        logger.warning("Failed to update user preference for %s: %s", user_id, e)
        return

    try:
        if existing:
            point = existing[0]
            old_vector = point.vector
            if isinstance(old_vector, dict):
                old_vector = list(old_vector.values())[0]
            total = point.payload.get("total_accepts", 0) + point.payload.get(
                "total_rejects", 0
            )
            weight = 1.0 / (total + 1) if action == "accept" else -0.5 / (total + 1)
            new_vector = [
                o + weight * (r - o) for o, r in zip(old_vector, recipe_vector)
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
                            "domain": "recipe",
                            "total_accepts": point.payload.get("total_accepts", 0)
                            + (1 if action == "accept" else 0),
                            "total_rejects": point.payload.get("total_rejects", 0)
                            + (1 if action == "reject" else 0),
                        },
                    )
                ],
            )
        else:
            if action == "reject":
                # Don't create a preference vector toward a disliked recipe.
                # Only update existing preferences on reject.
                return
            client.upsert(
                collection_name="user_preferences",
                points=[
                    models.PointStruct(
                        id=str(uuid.uuid4()),
                        vector=recipe_vector,
                        payload={
                            "user_id": user_id,
                            "household_id": household_id,
                            "domain": "recipe",
                            "total_accepts": 1,
                            "total_rejects": 0,
                        },
                    )
                ],
            )
    except Exception as e:
        logger.warning("Failed to upsert user preference for %s: %s", user_id, e)
