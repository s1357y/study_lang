"""StudySession CRUD — 하루 학습 세션 저장소.

흐름:
- get_today: 오늘 날짜 세션 조회 (없으면 None)
- get_by_date: 임의 날짜 세션 조회 (복습 화면용)
- get_recent: 최근 N개 세션 목록 (히스토리 화면용)
- create: 새 세션 생성 (planned_problem_ids 로 오늘 풀 문제 목록 지정)
- add_completed: 완료한 문제 추가 — 리스트 재할당으로 dirty 플래그 트리거
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.study_session import StudySession


async def get_today(
    db: AsyncSession,
    *,
    user_id: UUID,
    today_date: date,
) -> StudySession | None:
    stmt = select(StudySession).where(
        StudySession.user_id == user_id,
        StudySession.date == today_date,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def create(
    db: AsyncSession,
    *,
    user_id: UUID,
    today_date: date,
    planned_problem_ids: list[str],
) -> StudySession:
    session = StudySession(
        user_id=user_id,
        date=today_date,
        planned_problem_ids=planned_problem_ids,
        completed_problem_ids=[],
    )
    db.add(session)
    await db.flush()
    return session


async def get_by_date(
    db: AsyncSession,
    *,
    user_id: UUID,
    target_date: date,
) -> StudySession | None:
    stmt = select(StudySession).where(
        StudySession.user_id == user_id,
        StudySession.date == target_date,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_recent(
    db: AsyncSession,
    *,
    user_id: UUID,
    limit: int = 7,
) -> list[StudySession]:
    stmt = (
        select(StudySession)
        .where(StudySession.user_id == user_id)
        .order_by(StudySession.date.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


def add_completed(session: StudySession, *, problem_id: UUID) -> None:
    # 리스트 재할당으로 SQLAlchemy ARRAY dirty 플래그 트리거
    session.completed_problem_ids = session.completed_problem_ids + [str(problem_id)]
