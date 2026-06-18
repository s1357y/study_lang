"""ReviewRecord CRUD — SRS 복습 상태 저장소.

흐름:
- get_or_create: 없으면 NEW 상태로 생성, 동시 삽입 경쟁은 IntegrityError 포착 후 재조회
- due_today: next_due_at <= now() 인 레코드를 우선순위 정렬로 최대 40개
- get_new_content_items: 아직 ReviewRecord 가 없는 ContentItem — 신규 학습 슬롯용
- delete_new_records_for_items: 배치 전 생성된 미학습 ReviewRecord 삭제 (배치 완료 시 정리용)
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import case, delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content_item import ContentItem
from app.models.review_record import ReviewRecord


async def get_or_create(
    db: AsyncSession,
    *,
    user_id: UUID,
    content_item_id: UUID,
) -> ReviewRecord:
    # 기존 레코드 조회
    stmt = select(ReviewRecord).where(
        ReviewRecord.user_id == user_id,
        ReviewRecord.content_item_id == content_item_id,
    )
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()
    if record is not None:
        return record

    # 없으면 NEW 상태로 생성, 경쟁 조건 방어
    try:
        record = ReviewRecord(user_id=user_id, content_item_id=content_item_id)
        db.add(record)
        await db.flush()
        return record
    except IntegrityError:
        # 동시 삽입 시 UniqueConstraint 위반 → 재조회
        await db.rollback()
        result = await db.execute(stmt)
        return result.scalar_one()


async def due_today(
    db: AsyncSession,
    *,
    user_id: UUID,
    limit: int = 40,
) -> list[ReviewRecord]:
    # LEARNING/RELEARNING 우선, 그 다음 lapses 많은 순, 마지막으로 due 빠른 순
    priority = case(
        (ReviewRecord.state.in_(["LEARNING", "RELEARNING"]), 0),
        else_=1,
    )
    stmt = (
        select(ReviewRecord)
        .where(
            ReviewRecord.user_id == user_id,
            ReviewRecord.next_due_at <= func.now(),
        )
        .order_by(priority, ReviewRecord.lapses.desc(), ReviewRecord.next_due_at.asc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_new_content_items(
    db: AsyncSession,
    *,
    user_id: UUID,
    level: str,
    limit: int,
) -> list[ContentItem]:
    # 해당 사용자의 ReviewRecord 가 없는 ContentItem 만 조회 (신규 학습용)
    already_reviewed = select(ReviewRecord.content_item_id).where(ReviewRecord.user_id == user_id)
    stmt = (
        select(ContentItem)
        .where(
            ContentItem.level == level,
            ContentItem.id.notin_(already_reviewed),
        )
        .order_by(ContentItem.created_at.asc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def delete_new_records_for_items(
    db: AsyncSession,
    *,
    user_id: UUID,
    content_item_ids: list[UUID],
) -> int:
    """배치 전 생성된 미학습 ReviewRecord 삭제. 실제 학습 진행분(reps>0)은 건드리지 않는다."""
    if not content_item_ids:
        return 0
    stmt = delete(ReviewRecord).where(
        ReviewRecord.user_id == user_id,
        ReviewRecord.content_item_id.in_(content_item_ids),
        ReviewRecord.state == "NEW",
        ReviewRecord.last_reviewed_at.is_(None),
        ReviewRecord.reps == 0,
    )
    result = await db.execute(stmt)
    return result.rowcount
