"""SRS 서비스 — py-fsrs 를 이용한 복습 스케줄링.

흐름:
- determine_rating: 정답 여부 + 응답시간 분포로 Again/Hard/Good/Easy 결정
- schedule_next: ReviewRecord 에 py-fsrs 계산 결과 반영 후 flush
- get_due_today: review_repo.due_today 위임

py-fsrs API 주의:
- Card 에 reps/lapses 없음 → ReviewRecord 에서 수동 추적
- State enum 에 New 없음 (Learning=1, Review=2, Relearning=3)
  → DB "NEW" 상태는 fresh Card() 로 처리 (미복습 카드)
- due/last_review 는 항상 timezone-aware UTC
"""

from __future__ import annotations

import statistics
from datetime import UTC
from uuid import UUID

from fsrs import Card, Rating, Scheduler, State
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.review_record import ReviewRecord
from app.repositories import attempt_repo, review_repo

# DB 상태 문자열 ↔ py-fsrs State enum 변환 테이블
# "NEW" 는 py-fsrs 에 없는 내부 상태 — fresh Card() 로 처리
_STATE_TO_FSRS: dict[str, State] = {
    "LEARNING": State.Learning,
    "REVIEW": State.Review,
    "RELEARNING": State.Relearning,
}
_FSRS_TO_STATE: dict[State, str] = {v: k for k, v in _STATE_TO_FSRS.items()}


def _record_to_card(record: ReviewRecord) -> Card:
    # NEW 상태(미복습)는 fresh Card() 그대로 반환 — stability=0 설정 시 ZeroDivisionError 발생
    if record.state == "NEW":
        return Card()

    # 기존 복습 카드: DB 값으로 Card 재구성
    card = Card()
    card.stability = record.stability
    card.difficulty = record.difficulty
    fsrs_state = _STATE_TO_FSRS.get(record.state)
    if fsrs_state is not None:
        card.state = fsrs_state
    if record.last_reviewed_at is not None:
        card.last_review = record.last_reviewed_at
    return card


async def determine_rating(
    db: AsyncSession,
    *,
    user_id: UUID,
    problem_type: str,
    correct: bool,
    response_time_ms: int,
) -> Rating:
    # 오답이면 무조건 Again
    if not correct:
        return Rating.Again

    # 최근 30개 응답시간 조회 — 샘플 부족하면 Good 으로 귀결
    times = await attempt_repo.get_recent_response_times(
        db, user_id=user_id, problem_type=problem_type, limit=30
    )
    if len(times) < 10:
        return Rating.Good

    median = statistics.median(times)
    if response_time_ms <= median * 0.6:
        return Rating.Easy
    if response_time_ms >= median * 1.5:
        return Rating.Hard
    return Rating.Good


async def schedule_next(
    db: AsyncSession,
    *,
    record: ReviewRecord,
    rating: Rating,
) -> ReviewRecord:
    card = _record_to_card(record)

    # Scheduler().review_card(card, rating) → (updated_card, review_log)
    updated_card, _ = Scheduler().review_card(card, rating)

    # 결과를 ReviewRecord 에 반영
    record.stability = updated_card.stability
    record.difficulty = updated_card.difficulty
    record.state = _FSRS_TO_STATE.get(updated_card.state, "LEARNING")
    record.last_reviewed_at = updated_card.last_review

    # reps/lapses 는 Card 에 없으므로 수동 추적
    record.reps += 1
    if rating == Rating.Again:
        record.lapses += 1

    # due 는 항상 timezone-aware UTC 이지만 방어적으로 보정
    due = updated_card.due
    if due.tzinfo is None:
        due = due.replace(tzinfo=UTC)
    record.next_due_at = due

    await db.flush()
    return record


async def get_due_today(
    db: AsyncSession,
    *,
    user_id: UUID,
) -> list[ReviewRecord]:
    return await review_repo.due_today(db, user_id=user_id, limit=40)
