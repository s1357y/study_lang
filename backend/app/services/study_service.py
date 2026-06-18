"""Study 서비스 — 오늘 세션 빌드, 시도 제출, 통계 조회, 복습.

흐름:
- build_today_session: 기존 세션 재사용 또는 복습+신규 슬롯으로 신규 세션 생성
- record_attempt: SRS 갱신 + 약점 기록 + 세션 진행도 갱신 + DB commit
- get_stats: 오늘 due 수 / 신규 가능 수 / 약점 태그 반환
- get_session_review: 날짜별 완료 문제 복습 카드 목록
- get_recent_sessions: 최근 세션 요약 목록

에러:
- StudyError(code="not_found"): 존재하지 않는 Problem ID 제출 시
- StudyError(code="invalid_date"): 날짜 형식 오류 시
- StudyError(code="session_not_found"): 해당 날짜 세션 없음
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.study import ContentItemPayload, ReviewItemOut, SessionSummaryOut
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


# 생성 시점에 distractors가 선저장된 문제 유형 — 세션 빌드 시 풀 선택 불필요
_PRE_STORED_TYPES = frozenset(
    {
        ProblemType.MCQ_GRAMMAR,
        ProblemType.MCQ_CONTEXT,
        ProblemType.MCQ_SYNONYM,
    }
)


def _select_distractors(
    problem: Problem,
    item: ContentItem,
    pool: list[ContentItem],
) -> list[str]:
    """MCQ 유형 오답 선택지 3개를 반환.

    선저장 유형(MCQ_GRAMMAR·MCQ_CONTEXT·MCQ_SYNONYM)은 problem.distractors 에서 직접 읽고,
    동적 선택 유형(MCQ_MEANING·MCQ_READING)은 pool 에서 추출한다.
    MCQ_MEANING 이 선저장 distractors 를 가지면 pool 없이 바로 반환한다.
    """
    # MCQ_MEANING 선저장 distractors — 풀이 3개 초과면 랜덤 3개 선택해 세션마다 다른 조합 노출
    if problem.type == ProblemType.MCQ_MEANING and problem.distractors:
        opts = (problem.distractors or {}).get("options", [])
        return random.sample(opts, 3) if len(opts) > 3 else opts

    # 선저장 유형 — distractors JSONB에서 읽기
    if problem.type in _PRE_STORED_TYPES:
        return (problem.distractors or {}).get("options", [])

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
    # 랜덤 선택 — 세션마다 다양한 문제 유형 노출
    problem_map = await content_repo.get_random_problem_per_item(db, content_item_ids)
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
        if problem.type in _PRE_STORED_TYPES:
            # 선저장 유형은 pool 조회 없이 distractors에서 직접 추출
            distractors = _select_distractors(problem, item, [])
        elif problem.type in (ProblemType.MCQ_MEANING, ProblemType.MCQ_READING):
            # MCQ_MEANING에 선저장 distractors가 있으면 pool 쿼리 자체를 건너뜀
            if problem.type == ProblemType.MCQ_MEANING and problem.distractors:
                distractors = _select_distractors(problem, item, [])
            else:
                pool = await content_repo.get_items_by_level_excluding(
                    db, level=item.level, exclude_id=item.id, kind=item.kind, limit=20
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
        if p.type in _PRE_STORED_TYPES:
            # 선저장 유형 — JSONB에서 직접 추출 (pool 조회 불필요)
            distractors = _select_distractors(p, item, [])
        elif p.type in (ProblemType.MCQ_MEANING, ProblemType.MCQ_READING):
            # MCQ_MEANING에 선저장 distractors가 있으면 pool 쿼리 자체를 건너뜀
            if p.type == ProblemType.MCQ_MEANING and p.distractors:
                distractors = _select_distractors(p, item, [])
            else:
                pool = await content_repo.get_items_by_level_excluding(
                    db, level=item.level, exclude_id=item.id, kind=item.kind, limit=20
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


async def extend_today_session(
    db: AsyncSession,
    user: User,
    *,
    extra: int = 10,
) -> tuple[StudySession, list[ProblemWithDistractors]]:
    """오늘 세션에 추가 문제를 붙인다. 풀 소진 시 LLM으로 신규 어휘 생성 후 재시도."""
    from app.services import generation_service  # 순환 임포트 방지

    today = datetime.now(UTC).date()
    session = await study_session_repo.get_today(db, user_id=user.id, today_date=today)
    if session is None:
        raise StudyError("오늘 세션이 없습니다.", code="session_not_found")

    new_items = await review_repo.get_new_content_items(
        db, user_id=user.id, level=user.level, limit=extra
    )
    if not new_items:
        # 콘텐츠 풀 소진 → LLM으로 신규 어휘 생성 후 재사용
        logger.info("콘텐츠 풀 소진 — LLM 생성 시작: level=%s", user.level)
        new_items = await generation_service.generate_vocabulary(
            db, level=user.level, tags=[], count=extra
        )
    if not new_items:
        raise StudyError("추가 학습 콘텐츠를 생성하지 못했습니다.", code="no_more_content")

    for ci in new_items:
        await review_repo.get_or_create(db, user_id=user.id, content_item_id=ci.id)

    new_cids = [ci.id for ci in new_items]
    new_problems, new_planned_ids = await _build_problems_with_distractors(db, new_cids)

    # ARRAY 더티 플래그 트리거 — list 재할당 필요
    existing_planned = session.planned_problem_ids
    session.planned_problem_ids = existing_planned + new_planned_ids

    existing_problems = await _reload_session_problems(db, existing_planned)
    await db.commit()
    return session, existing_problems + new_problems


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


async def get_session_review(
    db: AsyncSession,
    *,
    user_id: UUID,
    date_str: str,
) -> list[ReviewItemOut]:
    """날짜별 완료 문제 복습 카드 목록 반환."""
    from datetime import date as date_type

    try:
        target_date = date_type.fromisoformat(date_str)
    except ValueError as exc:
        raise StudyError(f"잘못된 날짜 형식: {date_str}", code="invalid_date") from exc

    session = await study_session_repo.get_by_date(db, user_id=user_id, target_date=target_date)
    if session is None:
        raise StudyError(f"{date_str} 세션이 없습니다.", code="session_not_found")

    completed_ids = [UUID(pid) for pid in session.completed_problem_ids]
    if not completed_ids:
        return []

    problems = await content_repo.get_problems_by_ids(db, completed_ids)
    problem_map = {p.id: p for p in problems}

    citem_map = await content_repo.get_items_by_ids(db, [p.content_item_id for p in problems])

    attempt_map = await attempt_repo.get_by_problem_ids(
        db, user_id=user_id, problem_ids=completed_ids
    )

    items: list[ReviewItemOut] = []
    for pid in completed_ids:
        problem = problem_map.get(pid)
        if problem is None:
            continue
        ci = citem_map.get(problem.content_item_id)
        if ci is None:
            continue
        attempt = attempt_map.get(pid)
        items.append(
            ReviewItemOut(
                problem_id=problem.id,
                content_item_id=problem.content_item_id,
                problem_type=problem.type.value,
                prompt=problem.prompt,
                answer=problem.answer,
                tags=problem.tags,
                payload=ContentItemPayload(**ci.payload),
                my_correct=attempt.correct if attempt else None,
                my_rating=attempt.rating if attempt else None,
                attempted_at=attempt.created_at if attempt else None,
            )
        )
    return items


async def get_recent_sessions(
    db: AsyncSession,
    *,
    user_id: UUID,
    limit: int = 7,
) -> list[SessionSummaryOut]:
    """최근 세션 요약 목록 반환."""
    sessions = await study_session_repo.get_recent(db, user_id=user_id, limit=limit)
    return [
        SessionSummaryOut(
            id=s.id,
            date=s.date,
            completed_count=len(s.completed_problem_ids),
            total_count=len(s.planned_problem_ids),
            started_at=s.started_at,
            finished_at=s.finished_at,
        )
        for s in sessions
    ]
