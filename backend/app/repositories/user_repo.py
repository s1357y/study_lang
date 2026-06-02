"""User 테이블 접근 — DB CRUD 만 담당한다."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


async def get_by_email(db: AsyncSession, email: str) -> User | None:
    # 이메일 unique 인덱스를 이용해 단일 조회
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_by_id(db: AsyncSession, user_id: UUID) -> User | None:
    return await db.get(User, user_id)


async def create(db: AsyncSession, *, email: str, password_hash: str) -> User:
    # 호출자(서비스)가 트랜잭션 커밋을 제어 — 여기선 add + flush 까지만
    user = User(email=email, password_hash=password_hash)
    db.add(user)
    await db.flush()
    return user
