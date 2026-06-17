"""User 모델 — 이메일/비밀번호 인증의 기본 단위."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class User(Base):
    __tablename__ = "user"

    # 식별자 — UUID 를 PK 로 둬 외부 노출 안전
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)

    # 이메일은 unique, 검색 인덱스를 자동 생성
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)

    # argon2id 해시 문자열 (salt + 파라미터 포함). 평문 저장 절대 금지.
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    # 이메일 인증 도입 전엔 항상 NULL — 컬럼만 미리 보관
    email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # 학습 메타 — MVP 는 일본어 기본
    target_language: Mapped[str] = mapped_column(String(8), nullable=False, default="ja")
    level: Mapped[str] = mapped_column(String(32), nullable=False, default="BEGINNER")
    # 배치 시험을 한 번이라도 완료(또는 건너뜀)했는지 여부
    placement_done: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    # 타임스탬프 — DB 측 기본값을 사용해 INSERT 시 자동 채움
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
