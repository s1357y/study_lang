"""RefreshToken 모델 — 회전(rotation) + family 추적.

설계 의도:
- `id` 는 JWT 의 `jti` 와 동일 — DB 조회 키이자 토큰 식별자
- 평문 토큰은 저장 안 함. 대신 sha256 해시(`token_hash`) 만 보관
- 같은 로그인 세션의 회전 토큰들은 `family_id` 공유
- 재사용(revoked 토큰 재제출) 감지 시 family 전체 폐기
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class RefreshToken(Base):
    __tablename__ = "refresh_token"

    # JWT 의 jti 와 동일한 값
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # sha256(refresh_jwt) — 평문 토큰은 절대 저장하지 않음. 128 은 SHA512 전환 시에도 여유.
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False)

    # 동일 로그인 세션을 공유하는 토큰들의 그룹 id (재사용 감지의 단위)
    family_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)

    # 이 토큰이 회전돼서 나온 직전 토큰의 id (NULL = 로그인으로 시작된 family 의 첫 토큰)
    parent_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)

    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # revoked_at IS NULL 이면 활성 — 회전·로그아웃·재사용감지 시 채워짐
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)

    __table_args__ = (
        # refresh 회전·재사용 감지 조회의 핵심 인덱스
        Index("ix_refresh_user_family_revoked", "user_id", "family_id", "revoked_at"),
    )
