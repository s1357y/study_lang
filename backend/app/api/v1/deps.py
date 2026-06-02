"""공통 FastAPI Depends.

흐름:
- get_db: 요청당 AsyncSession 제공
- current_user_claims: Bearer access 토큰 디코딩만 (DB 미접근, 가벼움)
- current_user: claims + DB User 조회 (사용자 객체가 필요한 라우트용)
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db as _get_db
from app.core.security import AccessClaims, InvalidTokenError, decode_access
from app.models.user import User
from app.repositories import user_repo


async def get_db() -> AsyncIterator[AsyncSession]:
    # 별도 래퍼 — 추후 SAVEPOINT/테스트 등 주입 지점이 필요할 때 여기서 분기
    async for session in _get_db():
        yield session


async def current_user_claims(
    authorization: str | None = Header(default=None),
) -> AccessClaims:
    # Bearer 형식 검증 후 access 토큰만 통과
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )
    token = authorization.split(" ", 1)[1].strip()
    try:
        return decode_access(token)
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
        ) from exc


async def current_user(
    claims: AccessClaims = Depends(current_user_claims),
    db: AsyncSession = Depends(get_db),
) -> User:
    # claims.sub → DB User 조회. 사용자가 삭제된 경우 401 처리.
    user = await user_repo.get_by_id(db, UUID(claims.sub))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer exists",
        )
    return user
