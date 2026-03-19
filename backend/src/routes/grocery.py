"""Grocery list and item management."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..dependencies import Pagination, get_household_id, get_pagination
from ..models.grocery import GroceryItem, GroceryList
from ..schemas.grocery import (
    BulkCheckRequest,
    BulkItemCreateRequest,
    BulkUpdateResponse,
    GroceryItemResponse,
    GroceryItemUpdate,
    GroceryListCreate,
    GroceryListResponse,
)

router = APIRouter(prefix="/api/v1/grocery", tags=["grocery"])


@router.get("/lists", response_model=list[GroceryListResponse])
async def get_lists(
    household_id: uuid.UUID = Depends(get_household_id),
    pagination: Pagination = Depends(get_pagination),
    session: AsyncSession = Depends(get_db),
):
    lists_result = await session.execute(
        select(GroceryList)
        .where(GroceryList.household_id == household_id)
        .order_by(GroceryList.id)
        .offset(pagination.offset)
        .limit(pagination.limit)
    )
    lists = lists_result.scalars().all()
    if not lists:
        return []
    list_ids = [gl.id for gl in lists]
    items_result = await session.execute(
        select(GroceryItem).where(GroceryItem.grocery_list_id.in_(list_ids))
    )
    all_items = items_result.scalars().all()
    items_by_list: dict[uuid.UUID, list[GroceryItem]] = {}
    for item in all_items:
        items_by_list.setdefault(item.grocery_list_id, []).append(item)
    return [
        GroceryListResponse(
            id=gl.id,
            name=gl.name,
            estimated_total=gl.estimated_total,
            items=[
                GroceryItemResponse(
                    id=i.id,
                    ingredient_name=i.ingredient_name,
                    quantity=i.quantity,
                    category=i.category,
                    is_checked=i.is_checked,
                )
                for i in items_by_list.get(gl.id, [])
            ],
        )
        for gl in lists
    ]


@router.post("/lists", response_model=GroceryListResponse, status_code=201)
async def create_list(
    body: GroceryListCreate,
    household_id: uuid.UUID = Depends(get_household_id),
    session: AsyncSession = Depends(get_db),
):
    grocery_list = GroceryList(name=body.name, household_id=household_id)
    session.add(grocery_list)
    await session.commit()
    await session.refresh(grocery_list)
    return GroceryListResponse(
        id=grocery_list.id,
        name=grocery_list.name,
        estimated_total=grocery_list.estimated_total,
        items=[],
    )


@router.patch("/items/bulk", response_model=BulkUpdateResponse)
async def bulk_update_items(
    body: BulkCheckRequest,
    household_id: uuid.UUID = Depends(get_household_id),
    session: AsyncSession = Depends(get_db),
):
    item_ids = [u.item_id for u in body.updates]
    items_result = await session.execute(
        select(GroceryItem).where(GroceryItem.id.in_(item_ids))
    )
    items = items_result.scalars().all()
    item_map = {i.id: i for i in items}

    list_ids = {i.grocery_list_id for i in items}
    lists_result = await session.execute(
        select(GroceryList).where(GroceryList.id.in_(list_ids))
    )
    lists = lists_result.scalars().all()
    valid_list_ids = {gl.id for gl in lists if gl.household_id == household_id}

    updated = []
    for update in body.updates:
        item = item_map.get(update.item_id)
        if item and item.grocery_list_id in valid_list_ids:
            item.is_checked = update.is_checked
            session.add(item)
            updated.append(item.id)

    await session.commit()
    return {"updated_count": len(set(updated))}


@router.patch("/items/{item_id}", response_model=GroceryItemResponse)
async def update_item(
    item_id: uuid.UUID,
    body: GroceryItemUpdate,
    household_id: uuid.UUID = Depends(get_household_id),
    session: AsyncSession = Depends(get_db),
):
    item = await session.get(GroceryItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    grocery_list = await session.get(GroceryList, item.grocery_list_id)
    if not grocery_list or grocery_list.household_id != household_id:
        raise HTTPException(status_code=404, detail="Item not found")
    if body.is_checked is not None:
        item.is_checked = body.is_checked
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item


@router.post(
    "/lists/{list_id}/items/bulk",
    response_model=list[GroceryItemResponse],
    status_code=201,
)
async def bulk_add_items(
    list_id: uuid.UUID,
    body: BulkItemCreateRequest,
    household_id: uuid.UUID = Depends(get_household_id),
    session: AsyncSession = Depends(get_db),
):
    grocery_list = await session.get(GroceryList, list_id)
    if not grocery_list or grocery_list.household_id != household_id:
        raise HTTPException(status_code=404, detail="Grocery list not found")

    created = []
    for item_data in body.items:
        item = GroceryItem(
            grocery_list_id=list_id,
            ingredient_name=item_data.ingredient_name,
            quantity=item_data.quantity,
            category=item_data.category,
        )
        session.add(item)
        created.append(item)

    await session.commit()
    for item in created:
        await session.refresh(item)

    return [
        GroceryItemResponse(
            id=i.id,
            ingredient_name=i.ingredient_name,
            quantity=i.quantity,
            category=i.category,
            is_checked=i.is_checked,
        )
        for i in created
    ]
