"""콘텐츠 라우트 — Phase 3 검증용.

엔드포인트:
- POST /api/v1/content/generate : 즉시 콘텐츠 생성 (인증 필요)
- GET  /api/v1/content/pool     : 레벨별 풀 통계

Phase 4 이후 /sessions/today 가 이 서비스를 내부적으로 호출하게 된다.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import current_user, get_db
from app.api.v1.schemas.content import (
    ContentItemResponse,
    GenerateRequest,
    PoolStatsResponse,
)
from app.models.user import User
from app.services import content_service

router = APIRouter()


@router.post("/generate", response_model=list[ContentItemResponse])
async def generate_content(
    body: GenerateRequest,
    _user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> list:
    # 인증된 사용자의 요청으로 콘텐츠 생성 (or 풀에서 조회)
    items = await content_service.get_or_generate(
        db,
        level=body.level,
        tags=body.tags,
        count=body.count,
    )
    return items


@router.get("/pool", response_model=PoolStatsResponse)
async def pool_stats(
    _user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> PoolStatsResponse:
    # 레벨별 콘텐츠 수 반환 — 워커 동작 여부 확인용
    by_level = await content_service.get_pool_stats(db)
    return PoolStatsResponse(
        total=sum(by_level.values()),
        by_level=by_level,
    )
