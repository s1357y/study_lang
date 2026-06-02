"""DB 세션 단일 진입점.

흐름:
- create_async_engine 으로 단일 엔진 생성 (앱 생명주기 공유)
- async_sessionmaker 로 세션 팩토리 구성
- get_db 의존성이 요청당 1세션을 제공하고 종료 시 닫음
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

# 엔진은 앱 전체에서 1개 공유 (커넥션 풀 관리)
engine = create_async_engine(
    settings.database_url_async,
    pool_pre_ping=True,
    future=True,
)

# 세션 팩토리 — autoflush 는 끔 (명시적 flush/commit 권장)
SessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncIterator[AsyncSession]:
    # FastAPI Depends 용 — 요청 처리가 끝나면 세션을 닫고 풀로 반환
    async with SessionLocal() as session:
        yield session
