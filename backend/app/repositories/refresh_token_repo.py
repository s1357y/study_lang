"""RefreshToken 테이블 접근 — 회전·재사용 감지에 필요한 쿼리들.

서비스 계층(auth_service)이 이 함수들을 조합해 회전 로직을 수행한다.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.refresh_token import RefreshToken


async def create(
    db: AsyncSession,
    *,
    jti: UUID,
    user_id: UUID,
    token_hash: str,
    family_id: UUID,
    expires_at: datetime,
    parent_id: UUID | None = None,
) -> RefreshToken:
    # JWT 의 jti 값을 PK 로 사용 — 디코딩 후 즉시 조회 가능
    row = RefreshToken(
        id=jti,
        user_id=user_id,
        token_hash=token_hash,
        family_id=family_id,
        parent_id=parent_id,
        expires_at=expires_at,
    )
    db.add(row)
    await db.flush()
    return row


async def get(db: AsyncSession, jti: UUID) -> RefreshToken | None:
    return await db.get(RefreshToken, jti)


async def revoke(
    db: AsyncSession,
    jti: UUID,
    *,
    reason: str,
) -> None:
    # 단일 토큰만 revoke — 회전 시 직전 토큰 무효화에 사용
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.id == jti, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(timezone.utc), revoked_reason=reason)
    )


async def revoke_family(
    db: AsyncSession,
    family_id: UUID,
    *,
    reason: str,
) -> int:
    # family 전체 폐기 — 로그아웃/재사용 감지 시 사용. 영향받은 행 수 반환.
    result = await db.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(timezone.utc), revoked_reason=reason)
    )
    return result.rowcount or 0


async def list_active_in_family(
    db: AsyncSession, family_id: UUID
) -> list[RefreshToken]:
    # 진단/디버그 용 — 운영에선 거의 쓰지 않음
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.family_id == family_id,
            RefreshToken.revoked_at.is_(None),
        )
    )
    return list(result.scalars().all())
