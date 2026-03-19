"""Meal polls — vote on recipes within households."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..dependencies import get_current_user, get_household_id
from ..models.poll import MealPoll, PollVote
from ..models.recipe import Recipe
from ..models.user import User
from ..schemas.poll import PollCreate, PollResponse, VoteRequest

router = APIRouter(prefix="/api/v1/polls", tags=["polls"])


@router.post("", response_model=PollResponse, status_code=201)
async def create_poll(
    body: PollCreate,
    user: User = Depends(get_current_user),
    household_id: uuid.UUID = Depends(get_household_id),
    session: AsyncSession = Depends(get_db),
):
    recipe = await session.get(Recipe, body.recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    if recipe.household_id is not None and recipe.household_id != household_id:
        raise HTTPException(status_code=404, detail="Recipe not found")
    poll = MealPoll(
        household_id=household_id, recipe_id=body.recipe_id, proposed_by=user.id
    )
    session.add(poll)
    await session.commit()
    await session.refresh(poll)
    return await _poll_response(poll, session)


@router.post("/{poll_id}/vote")
async def vote_on_poll(
    poll_id: uuid.UUID,
    body: VoteRequest,
    user: User = Depends(get_current_user),
    household_id: uuid.UUID = Depends(get_household_id),
    session: AsyncSession = Depends(get_db),
):
    poll = await session.get(MealPoll, poll_id)
    if not poll:
        raise HTTPException(status_code=404, detail="Poll not found")
    if poll.household_id != household_id:
        raise HTTPException(status_code=404, detail="Poll not found")
    if not poll.is_active:
        raise HTTPException(status_code=400, detail="Poll is closed")
    result = await session.execute(
        select(PollVote).where(PollVote.poll_id == poll_id, PollVote.user_id == user.id)
    )
    existing = result.scalars().first()
    if existing:
        existing.vote = body.vote
        session.add(existing)
    else:
        vote = PollVote(poll_id=poll_id, user_id=user.id, vote=body.vote)
        session.add(vote)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        # Only handle duplicate-vote race conditions
        # (unique constraint on poll_id+user_id).
        exc_str = str(exc).lower()
        if "unique" not in exc_str and "duplicate" not in exc_str:
            raise HTTPException(status_code=500, detail="Could not save vote") from exc
        result = await session.execute(
            select(PollVote).where(
                PollVote.poll_id == poll_id, PollVote.user_id == user.id
            )
        )
        existing = result.scalars().first()
        if not existing:
            raise HTTPException(status_code=500, detail="Could not save vote") from exc
        existing.vote = body.vote
        session.add(existing)
        await session.commit()
    return {"status": "voted"}


@router.get("/active", response_model=list[PollResponse])
async def get_active_polls(
    household_id: uuid.UUID = Depends(get_household_id),
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(MealPoll).where(
            MealPoll.household_id == household_id,
            MealPoll.is_active == True,  # noqa: E712
        )
    )
    polls = result.scalars().all()
    if not polls:
        return []
    poll_ids = [p.id for p in polls]
    votes_result = await session.execute(
        select(PollVote).where(PollVote.poll_id.in_(poll_ids))
    )
    all_votes = votes_result.scalars().all()
    votes_by_poll: dict[uuid.UUID, list[PollVote]] = {}
    for v in all_votes:
        votes_by_poll.setdefault(v.poll_id, []).append(v)
    return [_build_poll_response(p, votes_by_poll.get(p.id, [])) for p in polls]


async def _poll_response(poll: MealPoll, session: AsyncSession) -> PollResponse:
    result = await session.execute(select(PollVote).where(PollVote.poll_id == poll.id))
    votes = result.scalars().all()
    return _build_poll_response(poll, votes)


def _build_poll_response(poll: MealPoll, votes: list[PollVote]) -> PollResponse:
    return PollResponse(
        id=poll.id,
        recipe_id=poll.recipe_id,
        proposed_by=poll.proposed_by,
        is_active=poll.is_active,
        yes_votes=[v.user_id for v in votes if v.vote == "yes"],
        no_votes=[v.user_id for v in votes if v.vote == "no"],
    )
