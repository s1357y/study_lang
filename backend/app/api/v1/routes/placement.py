"""배치 시험 라우트.

엔드포인트:
- GET  /placement/problems : 레벨별 문제 출제 + placement_token 발급
- POST /placement/submit   : 답안 제출 → 레벨 배정
- POST /placement/skip     : 건너뛰기 → placement_done=True, 레벨 유지
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import current_user, get_db
from app.api.v1.schemas.placement import (
    PlacementProblemsOut,
    PlacementResultOut,
    PlacementSubmitIn,
)
from app.models.user import User
from app.services import placement_service
from app.services.placement_service import PlacementError

router = APIRouter()


def _placement_error_to_http(exc: PlacementError) -> HTTPException:
    if exc.code == "insufficient_content":
        return HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    if exc.code in ("invalid_token", "token_expired", "invalid_answers"):
        return HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/problems", response_model=PlacementProblemsOut)
async def get_placement_problems(
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> PlacementProblemsOut:
    try:
        return await placement_service.get_placement_problems(db, user=user)
    except PlacementError as exc:
        raise _placement_error_to_http(exc) from exc


@router.post("/submit", response_model=PlacementResultOut, status_code=status.HTTP_200_OK)
async def submit_placement(
    body: PlacementSubmitIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> PlacementResultOut:
    try:
        return await placement_service.submit_placement(db, user=user, payload=body)
    except PlacementError as exc:
        raise _placement_error_to_http(exc) from exc


@router.post("/skip", status_code=status.HTTP_204_NO_CONTENT)
async def skip_placement(
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await placement_service.skip_placement(db, user=user)
