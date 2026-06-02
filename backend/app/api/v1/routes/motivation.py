"""Motivation 라우트 — 동기부여 지표(스트릭·XP·레벨·주간 목표) 조회.

엔드포인트:
- GET /motivation : 현재 사용자의 MotivationState 반환
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import current_user, get_db
from app.api.v1.schemas.motivation import MotivationOut
from app.models.user import User
from app.services import motivation_service

router = APIRouter()


@router.get("", response_model=MotivationOut)
async def get_motivation(
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> MotivationOut:
    state = await motivation_service.get_state(db, user_id=user.id)
    return MotivationOut.model_validate(state)
