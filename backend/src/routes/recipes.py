"""Recipe CRUD, semantic search, discovery, recommendations, swipe."""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..dependencies import (
    Pagination,
    get_current_user,
    get_household_id,
    get_pagination,
)
from ..models.recipe import Recipe, RecipeIngredient, SwipeAction
from ..models.user import User
from ..schemas.recipe import RecipeCreate, RecipeResponse, SwipeRequest
from ..services.discovery_service import discover_with_context, get_discovery_metrics
from ..services.recipe_service import (
    get_recommendations,
    search_recipes_semantic,
    update_user_preference,
    upsert_recipe_embedding,
)

_logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/recipes", tags=["recipes"])


@router.post("", response_model=RecipeResponse, status_code=status.HTTP_201_CREATED)
async def create_recipe(
    body: RecipeCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    if user.household_id is None:
        raise HTTPException(
            status_code=400,
            detail="You must belong to a household before creating recipes",
        )
    # Single transaction for recipe + ingredients
    recipe = Recipe(
        title=body.title,
        description=body.description,
        cost=body.cost,
        time_minutes=body.time_minutes,
        type=body.type,
        image_url=body.image_url,
        household_id=user.household_id,
        created_by=user.id,
    )
    session.add(recipe)
    await session.flush()  # get recipe.id without committing

    for ing in body.ingredients:
        ingredient = RecipeIngredient(
            recipe_id=recipe.id, name=ing.name, quantity=ing.quantity, unit=ing.unit
        )
        session.add(ingredient)
    await session.commit()
    await session.refresh(recipe)

    # Best-effort Qdrant upsert — recipe is still usable via DB queries
    # if vector indexing fails (e.g. Qdrant offline).
    # upsert_recipe_embedding already handles exceptions internally.
    upsert_recipe_embedding(recipe, body.ingredients)
    return await _recipe_response(recipe, session)


@router.get("", response_model=list[RecipeResponse])
async def list_recipes(
    household_id: uuid.UUID = Depends(get_household_id),
    pagination: Pagination = Depends(get_pagination),
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(Recipe)
        .where((Recipe.household_id == household_id) | (Recipe.household_id.is_(None)))
        .order_by(func.random())
        .offset(pagination.offset)
        .limit(pagination.limit)
    )
    recipes = list(result.scalars().all())
    return await _recipe_responses(recipes, session)


@router.get("/search", response_model=list[RecipeResponse])
async def search_recipes(
    q: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    results = search_recipes_semantic(
        q, household_id=str(user.household_id) if user.household_id else None
    )
    recipe_ids = [uuid.UUID(r.id) for r in results]
    if not recipe_ids:
        return []
    result = await session.execute(
        select(Recipe).where(
            Recipe.id.in_(recipe_ids),
            (Recipe.household_id.is_(None))
            | (Recipe.household_id == user.household_id),
        )
    )
    recipes = list(result.scalars().all())
    # Preserve Qdrant relevance ordering
    recipe_map = {r.id: r for r in recipes}
    recipes = [recipe_map[rid] for rid in recipe_ids if rid in recipe_map]
    return await _recipe_responses(recipes, session)


@router.get("/discover", response_model=list[RecipeResponse])
async def discover(
    q: str | None = None,
    user: User = Depends(get_current_user),
    household_id: uuid.UUID = Depends(get_household_id),
    session: AsyncSession = Depends(get_db),
):
    results = await discover_with_context(
        str(user.id), session, target_text=q, household_id=str(household_id)
    )
    recipe_ids = [uuid.UUID(r.id) for r in results]
    if not recipe_ids:
        return []
    result = await session.execute(
        select(Recipe).where(
            Recipe.id.in_(recipe_ids),
            (Recipe.household_id.is_(None)) | (Recipe.household_id == household_id),
        )
    )
    recipe_map = {r.id: r for r in result.scalars().all()}
    recipes = [recipe_map[rid] for rid in recipe_ids if rid in recipe_map]
    return await _recipe_responses(recipes, session)


@router.get("/discovery-metrics")
async def discovery_metrics(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await get_discovery_metrics(str(user.id), session)


@router.get("/recommendations", response_model=list[RecipeResponse])
async def recommendations(
    user: User = Depends(get_current_user),
    household_id: uuid.UUID = Depends(get_household_id),
    session: AsyncSession = Depends(get_db),
):
    results = await get_recommendations(
        str(user.id), session, household_id=str(household_id)
    )
    recipe_ids = [uuid.UUID(r.id) for r in results]
    if not recipe_ids:
        return []
    result = await session.execute(
        select(Recipe).where(
            Recipe.id.in_(recipe_ids),
            (Recipe.household_id.is_(None)) | (Recipe.household_id == household_id),
        )
    )
    recipe_map = {r.id: r for r in result.scalars().all()}
    recipes = [recipe_map[rid] for rid in recipe_ids if rid in recipe_map]
    return await _recipe_responses(recipes, session)


@router.post("/{recipe_id}/swipe")
async def swipe_recipe(
    recipe_id: uuid.UUID,
    body: SwipeRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    recipe = await session.get(Recipe, recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    if recipe.household_id is not None and recipe.household_id != user.household_id:
        raise HTTPException(status_code=404, detail="Recipe not found")
    # Atomic upsert via ON CONFLICT
    stmt = pg_insert(SwipeAction).values(
        user_id=user.id, recipe_id=recipe_id, action=body.action
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_swipe_actions_user_recipe",
        set_={"action": stmt.excluded.action, "updated_at": stmt.excluded.updated_at},
    )
    await session.execute(stmt)
    await session.commit()
    update_user_preference(
        str(user.id),
        recipe,
        body.action,
        household_id=str(user.household_id) if user.household_id else None,
    )
    return {"status": "ok"}


@router.get("/{recipe_id}", response_model=RecipeResponse)
async def get_recipe(
    recipe_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    recipe = await session.get(Recipe, recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    if recipe.household_id is not None and recipe.household_id != user.household_id:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return await _recipe_response(recipe, session)


# ── Helpers ──────────────────────────────────────────────────


async def _recipe_responses(
    recipes: list[Recipe], session: AsyncSession
) -> list[RecipeResponse]:
    if not recipes:
        return []
    recipe_ids = [r.id for r in recipes]
    result = await session.execute(
        select(RecipeIngredient).where(RecipeIngredient.recipe_id.in_(recipe_ids))
    )
    all_ingredients = result.scalars().all()
    ingredients_by_recipe: dict[uuid.UUID, list] = {}
    for ing in all_ingredients:
        ingredients_by_recipe.setdefault(ing.recipe_id, []).append(ing)
    return [
        RecipeResponse(
            id=r.id,
            title=r.title,
            description=r.description,
            cost=float(r.cost),
            time_minutes=r.time_minutes,
            type=r.type,
            image_url=r.image_url,
            ingredients=[
                {"name": i.name, "quantity": i.quantity, "unit": i.unit}
                for i in ingredients_by_recipe.get(r.id, [])
            ],
        )
        for r in recipes
    ]


async def _recipe_response(recipe: Recipe, session: AsyncSession) -> RecipeResponse:
    return (await _recipe_responses([recipe], session))[0]
