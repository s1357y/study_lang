"""ReviewRecord 모델 — 사용자별 ContentItem SRS 복습 상태.

설계 의도:
- user_id + content_item_id 조합이 유일 (uq_review_user_content)
- py-fsrs 계산 결과인 stability/difficulty/reps/lapses/state 를 그대로 저장
- next_due_at 기반으로 오늘의 복습 큐를 조회 (ix_review_user_due)
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ReviewRecord(Base):
    __tablename__ = "review_record"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)

    # 소유 사용자
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
    )

    # 복습 대상 콘텐츠
    content_item_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("content_item.id", ondelete="CASCADE"),
        nullable=False,
    )

    # py-fsrs 스케줄링 파라미터
    stability: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    difficulty: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    reps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lapses: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # NEW | LEARNING | REVIEW | RELEARNING
    state: Mapped[str] = mapped_column(String(20), nullable=False, default="NEW")

    # 마지막 복습 시각 (아직 한 번도 안 했으면 NULL)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # 다음 복습 예정 시각 — 생성 직후엔 now() (즉시 복습 대상)
    next_due_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        # 사용자당 동일 콘텐츠 중복 방지
        UniqueConstraint("user_id", "content_item_id", name="uq_review_user_content"),
        # 오늘 복습 큐 조회 핵심 인덱스
        Index("ix_review_user_due", "user_id", "next_due_at"),
    )
