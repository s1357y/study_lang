"""Motivation 서비스 — 스트릭·XP·레벨·주간 목표 갱신.

흐름:
- record_attempt: 시도 완료 시 XP 적립 + 스트릭 갱신 + 주간 진행도 갱신
- get_state: MotivationState 조회 (없으면 기본값으로 생성)

레벨 공식: level = floor(sqrt(xp / 100)) + 1
XP: 정답 +10, 오답 +2
스트릭: 같은 날 → 유지, 전날 → +1, 그 외 → 1로 리셋
주간 진행도: response_time_ms 를 초로 환산하여 누적 (현 주 아니면 주기 리셋)
"""

from __future__ import annotations

import math
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.motivation_state import MotivationState
from app.repositories import motivation_repo

logger = get_logger(__name__)

# XP 적립량
_XP_CORRECT = 10
_XP_WRONG = 2


def _calc_level(xp: int) -> int:
    """xp 에서 레벨 계산 — L1: 0-99, L2: 100-399, L3: 400-899 ..."""
    return math.floor(math.sqrt(xp / 100)) + 1


def _week_start(d: date) -> date:
    """월요일 기준 주 시작일 반환."""
    return d - timedelta(days=d.weekday())


def _update_streak(state: MotivationState, today: date) -> None:
    """스트릭 갱신 — 같은 날 no-op, 전날 +1, 그 외 리셋."""
    last = state.last_streak_date
    if last is None:
        state.streak_days = 1
    elif last == today:
        return
    elif last == today - timedelta(days=1):
        state.streak_days += 1
    else:
        state.streak_days = 1
    state.last_streak_date = today


def _update_weekly(state: MotivationState, today: date, elapsed_seconds: int) -> None:
    """주간 진행도 갱신 — 새 주이면 주기 리셋 후 누적."""
    week_start = _week_start(today)
    if state.weekly_period_start != week_start:
        state.weekly_progress_seconds = 0
        state.weekly_period_start = week_start
    state.weekly_progress_seconds += elapsed_seconds


async def record_attempt(
    db: AsyncSession,
    *,
    user_id: UUID,
    correct: bool,
    response_time_ms: int,
) -> MotivationState:
    """시도 완료 시 XP·스트릭·주간 진행도를 갱신하고 flush."""
    state = await motivation_repo.get_or_create(db, user_id=user_id)
    today = datetime.now(UTC).date()

    # XP 적립 + 레벨 재계산
    state.xp += _XP_CORRECT if correct else _XP_WRONG
    state.level = _calc_level(state.xp)

    # 스트릭·주간 갱신
    _update_streak(state, today)
    _update_weekly(state, today, elapsed_seconds=max(1, response_time_ms // 1000))

    await motivation_repo.save(db, state)
    logger.debug(
        "동기부여 갱신: user=%s xp=%d level=%d streak=%d",
        user_id, state.xp, state.level, state.streak_days,
    )
    return state


async def get_state(db: AsyncSession, *, user_id: UUID) -> MotivationState:
    """MotivationState 반환 — 없으면 기본값으로 생성 후 반환."""
    return await motivation_repo.get_or_create(db, user_id=user_id)
