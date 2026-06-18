"""LevelUpRecord 모델 — 레벨업 시험 이력.

응시 자격(7일 쿨다운) 판단과 시험 결과 기록에 사용한다.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class LevelUpRecord(Base):
    __tablename__ = "level_up_record"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # 시험 당시 유저 레벨 (승급 출발점)
    from_level: Mapped[str] = mapped_column(String(32), nullable=False)
    # 목표 레벨
    to_level: Mapped[str] = mapped_column(String(32), nullable=False)

    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)  # 정답률 (0.0 ~ 1.0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
