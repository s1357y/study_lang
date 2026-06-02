"""MotivationState CRUD — 사용자별 동기부여 지표 저장소.

흐름:
- get_or_create: 없으면 기본값으로 생성, 동시 삽입 경쟁은 IntegrityError 포착 후 재조회
- save: flush 만 (commit 은 서비스 계층 책임)
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.motivation_state import MotivationState


async def get_or_create(db: AsyncSession, *, user_id: UUID) -> MotivationState:
    stmt = select(MotivationState).where(MotivationState.user_id == user_id)
    result = await db.execute(stmt)
    state = result.scalar_one_or_none()
    if state is not None:
        return state

    # 처음 접근 시 기본값으로 생성
    try:
        state = MotivationState(user_id=user_id)
        db.add(state)
        await db.flush()
        return state
    except IntegrityError:
        # 동시 삽입 경쟁 방어
        await db.rollback()
        result = await db.execute(stmt)
        return result.scalar_one()


async def get(db: AsyncSession, *, user_id: UUID) -> MotivationState | None:
    stmt = select(MotivationState).where(MotivationState.user_id == user_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def save(db: AsyncSession, state: MotivationState) -> MotivationState:
    db.add(state)
    await db.flush()
    return state
