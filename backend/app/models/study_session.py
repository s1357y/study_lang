"""StudySession 모델 — 하루 단위 학습 세션.

설계 의도:
- 사용자당 날짜별 하나의 세션만 허용 (uq_session_user_date)
- planned/completed problem ID 목록을 ARRAY(String) 으로 저장해 진행도 추적
- finished_at NULL 이면 진행 중, 설정되면 완료
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class StudySession(Base):
    __tablename__ = "study_session"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)

    # 세션 소유 사용자
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
    )

    # 세션 날짜 (날짜만, 시각 제외)
    date: Mapped[date] = mapped_column(Date, nullable=False)

    # 오늘 세션에서 풀기로 계획된 Problem UUID 문자열 목록
    planned_problem_ids: Mapped[list[str]] = mapped_column(
        ARRAY(String(36)), nullable=False, default=list
    )

    # 이미 완료한 Problem UUID 문자열 목록 — add_completed 로 추가
    completed_problem_ids: Mapped[list[str]] = mapped_column(
        ARRAY(String(36)), nullable=False, default=list
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # NULL 이면 세션 진행 중
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        # 사용자당 날짜 하나만 허용
        UniqueConstraint("user_id", "date", name="uq_session_user_date"),
    )
