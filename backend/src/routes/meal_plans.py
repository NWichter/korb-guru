"""Meal plan CRUD and grocery list generation."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..dependencies import Pagination, get_household_id, get_pagination
from ..models.grocery import GroceryItem
from ..models.meal_plan import MealPlan
from ..models.recipe import Recipe
from ..schemas.meal_plan import MealPlanCreate, MealPlanResponse
from ..services.grocery_service import generate_grocery_list as _generate_grocery_list

router = APIRouter(prefix="/api/v1/meal-plans", tags=["meal-plans"])


class GenerateGroceryListRequest(BaseModel):
    start_date: date
    end_date: date


@router.post("", response_model=MealPlanResponse)
async def add_to_plan(
    body: MealPlanCreate,
    household_id: uuid.UUID = Depends(get_household_id),
    session: AsyncSession = Depends(get_db),
):
    recipe = await session.get(Recipe, body.recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    if recipe.household_id is not None and recipe.household_id != household_id:
        raise HTTPException(
            status_code=403, detail="Recipe does not belong to your household"
        )
    plan = MealPlan(
        household_id=household_id,
        recipe_id=body.recipe_id,
        planned_date=body.planned_date,
        meal_slot=body.meal_slot,
    )
    session.add(plan)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail=(
                f"Meal slot '{body.meal_slot}' on {body.planned_date} is already taken"
            ),
        )
    await session.refresh(plan)
    return plan


@router.get("", response_model=list[MealPlanResponse])
async def get_meal_plans(
    start_date: date | None = None,
    end_date: date | None = None,
    household_id: uuid.UUID = Depends(get_household_id),
    pagination: Pagination = Depends(get_pagination),
    session: AsyncSession = Depends(get_db),
):
    query = select(MealPlan).where(MealPlan.household_id == household_id)
    if start_date:
        query = query.where(MealPlan.planned_date >= start_date)
    if end_date:
        query = query.where(MealPlan.planned_date <= end_date)
    result = await session.execute(
        query.order_by(MealPlan.planned_date, MealPlan.id)
        .offset(pagination.offset)
        .limit(pagination.limit)
    )
    return result.scalars().all()


@router.delete("/{plan_id}")
async def delete_plan(
    plan_id: uuid.UUID,
    household_id: uuid.UUID = Depends(get_household_id),
    session: AsyncSession = Depends(get_db),
):
    plan = await session.get(MealPlan, plan_id)
    if not plan or plan.household_id != household_id:
        raise HTTPException(status_code=404, detail="Plan not found")
    await session.delete(plan)
    await session.commit()
    return {"status": "deleted"}


@router.post("/generate-grocery-list")
async def generate_grocery_list(
    body: GenerateGroceryListRequest,
    household_id: uuid.UUID = Depends(get_household_id),
    session: AsyncSession = Depends(get_db),
):
    start, end = body.start_date, body.end_date
    if start > end:
        raise HTTPException(
            status_code=400,
            detail="start_date must not be after end_date",
        )
    grocery_list = await _generate_grocery_list(household_id, start, end, session)
    items_result = await session.execute(
        select(GroceryItem).where(GroceryItem.grocery_list_id == grocery_list.id)
    )
    items = items_result.scalars().all()
    return {
        "grocery_list_id": str(grocery_list.id),
        "item_count": len(items),
        "estimated_total": float(grocery_list.estimated_total),
    }
