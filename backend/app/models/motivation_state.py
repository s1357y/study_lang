"""MotivationState 모델 — 사용자별 동기부여 지표(스트릭·XP·레벨·주간 목표)."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class MotivationState(Base):
    __tablename__ = "motivation_state"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)

    # User 와 1:1 관계 — 중복 방지를 위해 unique 제약
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    # 스트릭 — 연속 학습 일수와 마지막 학습 날짜
    streak_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_streak_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # XP · 레벨 — level = floor(sqrt(xp / 100)) + 1
    xp: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # 주간 목표 — 목표(분) · 실적(초 단위 누적, API 반환 시 분으로 환산)
    weekly_goal_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    weekly_progress_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    weekly_period_start: Mapped[date | None] = mapped_column(Date, nullable=True)

    # 타임스탬프
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
