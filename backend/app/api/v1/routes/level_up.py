"""레벨업 시험 라우트.

엔드포인트:
- GET  /level-up/eligibility : 응시 자격 조회
- GET  /level-up/problems    : 시험 문제 발급 (HMAC 토큰 포함)
- POST /level-up/submit      : 답안 제출 + 결과 반환
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import current_user, get_db
from app.api.v1.schemas.level_up import (
    LevelUpEligibilityOut,
    LevelUpProblemsOut,
    LevelUpResultOut,
    LevelUpSubmitIn,
)
from app.models.user import User
from app.services import level_up_service
from app.services.level_up_service import LevelUpError

router = APIRouter()


def _level_up_error_to_http(exc: LevelUpError) -> HTTPException:
    if exc.code == "insufficient_content":
        return HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    if exc.code == "not_eligible":
        return HTTPException(status.HTTP_403_FORBIDDEN, detail=str(exc))
    if exc.code in ("invalid_token", "token_expired", "invalid_answers"):
        return HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/eligibility", response_model=LevelUpEligibilityOut)
async def get_eligibility(
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> LevelUpEligibilityOut:
    return await level_up_service.check_eligibility(db, user)


@router.get("/problems", response_model=LevelUpProblemsOut)
async def get_level_up_problems(
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> LevelUpProblemsOut:
    try:
        return await level_up_service.get_level_up_problems(db, user)
    except LevelUpError as exc:
        raise _level_up_error_to_http(exc) from exc


@router.post("/submit", response_model=LevelUpResultOut)
async def submit_level_up(
    body: LevelUpSubmitIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> LevelUpResultOut:
    try:
        return await level_up_service.submit_level_up(db, user=user, payload=body)
    except LevelUpError as exc:
        raise _level_up_error_to_http(exc) from exc
