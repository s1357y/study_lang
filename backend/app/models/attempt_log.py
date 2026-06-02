"""AttemptLog 모델 — 사용자가 문제를 풀 때마다 기록되는 시도 이력.

설계 의도:
- content_item_id 를 비정규화해 problem 조인 없이 태그 기반 집계 가능
- mistake_tags 로 오답 시 어떤 태그가 약점인지 즉시 파악
- ix_attempt_user_created 로 사용자별 최근 응답시간 조회 최적화
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AttemptLog(Base):
    __tablename__ = "attempt_log"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)

    # 시도한 사용자
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
    )

    # 풀었던 문제
    problem_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("problem.id", ondelete="CASCADE"),
        nullable=False,
    )

    # problem → content_item 조인 없이 집계하기 위한 비정규화 컬럼
    content_item_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("content_item.id", ondelete="CASCADE"),
        nullable=False,
    )

    # 정답 여부
    correct: Mapped[bool] = mapped_column(Boolean, nullable=False)

    # 풀이 소요 시간 (밀리초) — FSRS rating 결정에 활용
    response_time_ms: Mapped[int] = mapped_column(Integer, nullable=False)

    # FSRS 평가 결과 — Again | Hard | Good | Easy (NULL: 아직 미평가)
    rating: Mapped[str | None] = mapped_column(String(10), nullable=True)

    # 오답 원인 태그 (약점 집계용) — 정답이면 빈 배열
    mistake_tags: Mapped[list[str]] = mapped_column(
        ARRAY(String(100)), nullable=False, default=list
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        # 사용자별 최근 시도 이력 조회 핵심 인덱스
        Index("ix_attempt_user_created", "user_id", "created_at"),
    )
