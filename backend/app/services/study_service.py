"""Study 서비스 — 오늘 세션 빌드, 시도 제출, 통계 조회.

흐름:
- build_today_session: 기존 세션 재사용 또는 복습+신규 슬롯으로 신규 세션 생성
- record_attempt: SRS 갱신 + 약점 기록 + 세션 진행도 갱신 + DB commit
- get_stats: 오늘 due 수 / 신규 가능 수 / 약점 태그 반환

에러:
- StudyError(code="not_found"): 존재하지 않는 Problem ID 제출 시
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.content_item import ContentItem
from app.models.problem import Problem, ProblemType
from app.models.study_session import StudySession
from app.models.user import User
from app.repositories import attempt_repo, content_repo, review_repo, study_session_repo
from app.services import motivation_service, srs_service, weakness_service

logger = get_logger(__name__)

# 세션당 최대 신규 학습 슬롯
_NEW_ITEM_SLOTS = 10


class StudyError(Exception):
    """Study 도메인 예외. routes 가 HTTP 상태로 매핑한다."""

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass
class ProblemWithDistractors:
    problem: Problem
    distractors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# 내부 헬퍼
# ---------------------------------------------------------------------------


def _select_distractors(
    problem: Problem,
    item: ContentItem,
    pool: list[ContentItem],
) -> list[str]:
    """MCQ 유형 오답 선택지 3개를 pool 에서 추출."""
    if problem.type not in (ProblemType.MCQ_MEANING, ProblemType.MCQ_READING):
        return []

    correct_answer = problem.answer
    field_key = "meaning_ko" if problem.type == ProblemType.MCQ_MEANING else "reading"

    candidates: list[str] = []
    seen: set[str] = {correct_answer}
    for ci in pool:
        val = ci.payload.get(field_key, "")
        if val and val not in seen:
            seen.add(val)
            candidates.append(val)
        if len(candidates) >= 3:
            break
    return candidates


async def _build_problems_with_distractors(
    db: AsyncSession,
    content_item_ids: list[UUID],
) -> tuple[list[ProblemWithDistractors], list[str]]:
    """content_item_ids 로 ProblemWithDistractors 목록과 planned_problem_ids 반환."""
    problem_map = await content_repo.get_representative_problems(db, content_item_ids)
    citem_map = await content_repo.get_items_by_ids(db, content_item_ids)

    result: list[ProblemWithDistractors] = []
    planned_ids: list[str] = []

    for cid in content_item_ids:
        problem = problem_map.get(cid)
        if problem is None:
            logger.warning("ContentItem %s 에 Problem 없음, 세션에서 제외", cid)
            continue
        item = citem_map.get(cid)
        if item is None:
            continue

        distractors: list[str] = []
        if problem.type in (ProblemType.MCQ_MEANING, ProblemType.MCQ_READING):
            pool = await content_repo.get_items_by_level_excluding(
                db, level=item.level, exclude_id=item.id, limit=20
            )
            distractors = _select_distractors(problem, item, pool)

        result.append(ProblemWithDistractors(problem=problem, distractors=distractors))
        planned_ids.append(str(problem.id))

    return result, planned_ids


async def _reload_session_problems(
    db: AsyncSession,
    planned_ids: list[str],
) -> list[ProblemWithDistractors]:
    """기존 세션 재사용 시 planned_problem_ids 로 문제 목록 재구성."""
    if not planned_ids:
        return []

    uuids = [UUID(pid) for pid in planned_ids]
    problems = await content_repo.get_problems_by_ids(db, uuids)
    problem_by_id = {p.id: p for p in problems}
    citem_map = await content_repo.get_items_by_ids(db, list({p.content_item_id for p in problems}))

    out: list[ProblemWithDistractors] = []
    for pid in uuids:
        p = problem_by_id.get(pid)
        if p is None:
            continue
        item = citem_map.get(p.content_item_id)
        if item is None:
            continue
        distractors: list[str] = []
        if p.type in (ProblemType.MCQ_MEANING, ProblemType.MCQ_READING):
            pool = await content_repo.get_items_by_level_excluding(
                db, level=item.level, exclude_id=item.id, limit=20
            )
            distractors = _select_distractors(p, item, pool)
        out.append(ProblemWithDistractors(problem=p, distractors=distractors))
    return out


# ---------------------------------------------------------------------------
# 공개 API
# ---------------------------------------------------------------------------


async def build_today_session(
    db: AsyncSession,
    user: User,
) -> tuple[StudySession, list[ProblemWithDistractors]]:
    """오늘 세션이 있으면 재사용, 없으면 복습+신규 슬롯으로 새로 생성."""
    today = datetime.now(UTC).date()

    existing = await study_session_repo.get_today(db, user_id=user.id, today_date=today)
    if existing is not None:
        problems = await _reload_session_problems(db, existing.planned_problem_ids)
        return existing, problems

    # 복습 큐
    due_records = await srs_service.get_due_today(db, user_id=user.id)
    due_content_ids = [r.content_item_id for r in due_records]

    # 신규 슬롯 채우기
    new_slots = max(0, _NEW_ITEM_SLOTS - len(due_records))
    new_items: list[ContentItem] = []
    if new_slots > 0:
        new_items = await review_repo.get_new_content_items(
            db, user_id=user.id, level=user.level, limit=new_slots
        )

    # 신규 아이템 ReviewRecord 사전 생성
    for ci in new_items:
        await review_repo.get_or_create(db, user_id=user.id, content_item_id=ci.id)

    all_content_ids = due_content_ids + [ci.id for ci in new_items]
    problems_with_dist, planned_ids = await _build_problems_with_distractors(db, all_content_ids)

    session = await study_session_repo.create(
        db, user_id=user.id, today_date=today, planned_problem_ids=planned_ids
    )
    await db.commit()
    return session, problems_with_dist


async def record_attempt(
    db: AsyncSession,
    *,
    user_id: UUID,
    problem_id: UUID,
    content_item_id: UUID,
    correct: bool,
    response_time_ms: int,
) -> tuple:
    """시도 제출 → AttemptLog + ReviewRecord 반환. DB commit 포함."""
    problem = await content_repo.get_problem_by_id(db, problem_id)
    if problem is None:
        raise StudyError("Problem not found", code="not_found")

    rating = await srs_service.determine_rating(
        db,
        user_id=user_id,
        problem_type=problem.type.value,
        correct=correct,
        response_time_ms=response_time_ms,
    )

    mistake_tags = problem.tags if not correct else []
    log = await attempt_repo.create(
        db,
        user_id=user_id,
        problem_id=problem_id,
        content_item_id=content_item_id,
        correct=correct,
        response_time_ms=response_time_ms,
        rating=rating.name,
        mistake_tags=mistake_tags,
    )

    record = await review_repo.get_or_create(db, user_id=user_id, content_item_id=content_item_id)
    record = await srs_service.schedule_next(db, record=record, rating=rating)

    await weakness_service.record_attempt(db, user_id=user_id, tags=problem.tags, correct=correct)
    await motivation_service.record_attempt(
        db, user_id=user_id, correct=correct, response_time_ms=response_time_ms
    )

    today = datetime.now(UTC).date()
    today_session = await study_session_repo.get_today(db, user_id=user_id, today_date=today)
    if today_session is not None:
        study_session_repo.add_completed(today_session, problem_id=problem_id)

    await db.commit()
    return log, record


async def get_stats(
    db: AsyncSession,
    user: User,
) -> tuple[int, int, list[str]]:
    """(due_today, new_available, weak_tags) 반환."""
    due_records = await srs_service.get_due_today(db, user_id=user.id)
    new_items = await review_repo.get_new_content_items(
        db, user_id=user.id, level=user.level, limit=_NEW_ITEM_SLOTS
    )
    weak_tags = await weakness_service.get_weak_tags(db, user_id=user.id)
    return len(due_records), len(new_items), weak_tags
