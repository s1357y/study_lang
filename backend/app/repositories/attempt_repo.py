"""AttemptLog CRUD — 문제 시도 이력 저장소.

흐름:
- create: 새 시도 기록 삽입 후 flush
- get_recent_response_times: FSRS rating 결정을 위한 최근 응답시간 목록
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attempt_log import AttemptLog
from app.models.problem import Problem


async def create(
    db: AsyncSession,
    *,
    user_id: UUID,
    problem_id: UUID,
    content_item_id: UUID,
    correct: bool,
    response_time_ms: int,
    rating: str | None,
    mistake_tags: list[str],
) -> AttemptLog:
    log = AttemptLog(
        user_id=user_id,
        problem_id=problem_id,
        content_item_id=content_item_id,
        correct=correct,
        response_time_ms=response_time_ms,
        rating=rating,
        mistake_tags=mistake_tags,
    )
    db.add(log)
    await db.flush()
    return log


async def get_recent_response_times(
    db: AsyncSession,
    *,
    user_id: UUID,
    problem_type: str,
    limit: int = 30,
) -> list[int]:
    # 같은 유형의 문제에 대한 최근 응답시간만 조회 — Problem JOIN 필요
    stmt = (
        select(AttemptLog.response_time_ms)
        .join(Problem, AttemptLog.problem_id == Problem.id)
        .where(
            AttemptLog.user_id == user_id,
            Problem.type == problem_type,
        )
        .order_by(AttemptLog.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
