"""
GET /examples — read from Postgres example table (Alembic schema, apps/postgres/seed).
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db

router = APIRouter(tags=["examples"])


class ExampleItem(BaseModel):
    """One row from the example table."""

    id: int
    name: str
    created_at: datetime


@router.get("/examples", response_model=list[ExampleItem])
async def list_examples(db: AsyncSession = Depends(get_db)):
    """
    Return all rows from the example table (Postgres).
    Schema: apps/api/alembic. Seed: pnpm db:seed:postgres.
    """
    try:
        result = await db.execute(
            text("SELECT id, name, created_at FROM example ORDER BY id"),
        )
        rows = result.mappings().all()
        return [ExampleItem(**row) for row in rows]
    except Exception as e:
        msg = f"Database unavailable: {e!s}"
        raise HTTPException(status_code=503, detail=msg) from e
