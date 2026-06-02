"""UserProfile 모델 — 사용자별 약점 태그 통계.

설계 의도:
- tag_stats(JSONB) 에 태그별 시도 횟수/오답 수/최근 오답 시각을 누적
- User 에 인라인하지 않고 분리한 이유: 데이터 크기가 클 수 있고 별도 집계 로직이 필요
- JSONB 변경 시 반드시 flag_modified(profile, "tag_stats") 호출 필요 (SQLAlchemy 감지 트랩)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class UserProfile(Base):
    __tablename__ = "user_profile"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)

    # 1:1 관계 — 사용자당 프로필 하나
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # {"태그명": {"seen": 40, "wrong": 18, "last_wrong_at": "2024-01-01T00:00:00Z"}}
    tag_stats: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )

    # 사용자가 선호하는 학습 토픽 (프로필 설정용, 현재 미활용)
    preferred_topics: Mapped[list[str]] = mapped_column(
        ARRAY(String(100)), nullable=False, default=list
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
