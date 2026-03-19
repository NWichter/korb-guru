"""Route optimization — shopping route planning."""

import uuid as _uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..dependencies import get_current_user
from ..models.store import Store
from ..models.user import User
from ..schemas.route import (
    RouteLeg,
    RouteOptimizeRequest,
    RouteResponse,
    RouteStop,
)
from ..services.route_service import optimize_route as _optimize

router = APIRouter(prefix="/api/v1/route", tags=["route"])


@router.post("/optimize", response_model=RouteResponse)
async def optimize_route(
    body: RouteOptimizeRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    if not body.selected_shops:
        return RouteResponse(saved=0.0, time=0, stops=[])
    time_limit = max(body.time_limit, 5)

    # Separate valid UUIDs from plain name strings
    uuid_values: list[_uuid.UUID] = []
    name_values: list[str] = []
    for val in body.selected_shops:
        try:
            uuid_values.append(_uuid.UUID(val))
        except ValueError:
            name_values.append(val)

    found_stores: list[Store] = []
    if uuid_values:
        store_result = await session.execute(
            select(Store).where(Store.id.in_(uuid_values))
        )
        found_stores.extend(store_result.scalars().all())
    if name_values:
        name_result = await session.execute(
            select(Store).where(Store.name.in_(name_values))
        )
        found_stores.extend(name_result.scalars().all())

    # Return 400 if any requested shops could not be resolved
    found_ids = {str(s.id).lower() for s in found_stores}
    found_names = {s.name for s in found_stores}
    unmatched = [
        v
        for v in body.selected_shops
        if v.lower() not in found_ids and v not in found_names
    ]
    if unmatched:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown shops: {', '.join(unmatched)}",
        )
    shop_names = [s.name for s in found_stores]
    result = await _optimize(
        shop_names,
        time_limit,
        session,
        start_lat=body.start_lat,
        start_lng=body.start_lng,
        transport_mode=body.transport_mode,
    )
    return RouteResponse(
        saved=result["saved"],
        time=result["time"],
        stops=[RouteStop(**s) for s in result["stops"]],
        legs=[RouteLeg(**leg) for leg in result["legs"]],
        total_distance_m=result["total_distance_m"],
        total_duration_min=result["total_duration_min"],
    )


@router.get("/stores")
async def get_stores(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(select(Store))
    return result.scalars().all()
