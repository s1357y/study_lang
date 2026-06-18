"""레벨업 시험 서비스 — 응시 자격 확인, 시험 출제, 채점, 레벨 갱신.

흐름:
- check_eligibility: 학습량(30개+) + 쿨다운(7일) + 최고레벨 여부 확인
- get_level_up_problems: JLPT 형식 20문제 샘플링 + HMAC 토큰 발급
- submit_level_up: 토큰 검증 → 채점(70% 기준) → 합격 시 User.level 승급
"""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.level_up import (
    LevelUpEligibilityOut,
    LevelUpProblemOut,
    LevelUpProblemsOut,
    LevelUpResultOut,
    LevelUpSubmitIn,
)
from app.core.logging import get_logger
from app.models.content_item import ContentItem
from app.models.level_up_record import LevelUpRecord
from app.models.problem import Problem, ProblemType
from app.models.review_record import ReviewRecord
from app.models.user import User
from app.repositories import content_repo, user_repo
from app.services.placement_service import (
    _GRAMMAR_LEVELS,
    PlacementError,
    _sign_token,
    _verify_token,
)

logger = get_logger(__name__)

_LEVEL_SEQUENCE = ["BEGINNER", "ELEMENTARY", "INTERMEDIATE", "ADVANCED"]
_PASS_THRESHOLD = 0.70  # 70% (14/20)
_COOLDOWN_DAYS = 7
_MIN_STUDIED = 30  # 응시 최소 학습량


class LevelUpError(Exception):
    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


def _next_level(current: str) -> str | None:
    """다음 레벨 반환. 최고 레벨이면 None."""
    idx = _LEVEL_SEQUENCE.index(current) if current in _LEVEL_SEQUENCE else -1
    if idx < 0 or idx >= len(_LEVEL_SEQUENCE) - 1:
        return None
    return _LEVEL_SEQUENCE[idx + 1]


async def check_eligibility(
    db: AsyncSession,
    user: User,
) -> LevelUpEligibilityOut:
    """응시 자격 조회 — 학습량·쿨다운·최고레벨 세 조건을 모두 확인."""
    next_lvl = _next_level(user.level)
    if next_lvl is None:
        return LevelUpEligibilityOut(
            eligible=False,
            studied_count=0,
            required_count=_MIN_STUDIED,
            cooldown_until=None,
            next_level=None,
        )

    # 현재 레벨 ContentItem 중 실제 학습 완료(state != NEW) 개수
    stmt = (
        select(func.count())
        .select_from(ReviewRecord)
        .join(ContentItem, ReviewRecord.content_item_id == ContentItem.id)
        .where(
            ReviewRecord.user_id == user.id,
            ContentItem.level == user.level,
            ReviewRecord.state != "NEW",
        )
    )
    result = await db.execute(stmt)
    studied_count: int = result.scalar_one()

    # 7일 쿨다운 확인 — 가장 최근 시험 기록
    cooldown_stmt = (
        select(LevelUpRecord)
        .where(
            LevelUpRecord.user_id == user.id,
            LevelUpRecord.from_level == user.level,
        )
        .order_by(LevelUpRecord.created_at.desc())
        .limit(1)
    )
    last_record_result = await db.execute(cooldown_stmt)
    last_record = last_record_result.scalar_one_or_none()

    cooldown_until: datetime | None = None
    if last_record is not None:
        cooldown_end = last_record.created_at + timedelta(days=_COOLDOWN_DAYS)
        if datetime.now(UTC) < cooldown_end:
            cooldown_until = cooldown_end

    eligible = studied_count >= _MIN_STUDIED and cooldown_until is None

    return LevelUpEligibilityOut(
        eligible=eligible,
        studied_count=studied_count,
        required_count=_MIN_STUDIED,
        cooldown_until=cooldown_until,
        next_level=next_lvl,
    )


async def _fetch_problems(
    db: AsyncSession,
    *,
    level: str,
    problem_type: ProblemType,
    kind: str,
    limit: int,
) -> list[Problem]:
    return await content_repo.get_problems_for_placement(
        db, language="ja", level=level, problem_type=problem_type, kind=kind, limit=limit
    )


async def _build_exam_distractors(
    db: AsyncSession,
    problem: Problem,
    level: str,
) -> list[str]:
    """레벨업 시험 문제 오답 선택지 구성 — 배치 시험과 동일 로직."""
    pre_stored = {ProblemType.MCQ_GRAMMAR, ProblemType.MCQ_CONTEXT, ProblemType.MCQ_SYNONYM}
    if problem.type in pre_stored:
        return (problem.distractors or {}).get("options", [])

    # MCQ_MEANING 선저장 distractors — 풀이 3개 초과면 랜덤 3개 선택해 시험마다 다른 조합 노출
    if problem.type == ProblemType.MCQ_MEANING and problem.distractors:
        opts = (problem.distractors or {}).get("options", [])
        return random.sample(opts, 3) if len(opts) > 3 else opts

    if problem.type not in (ProblemType.MCQ_MEANING, ProblemType.MCQ_READING):
        return []

    pool = await content_repo.get_items_by_level_excluding(
        db, level=level, exclude_id=problem.content_item_id, kind="vocabulary", limit=20
    )
    field_key = "meaning_ko" if problem.type == ProblemType.MCQ_MEANING else "reading"
    seen: set[str] = {problem.answer}
    distractors: list[str] = []
    for ci in pool:
        val = ci.payload.get(field_key, "")
        if val and val not in seen:
            seen.add(val)
            distractors.append(val)
        if len(distractors) >= 3:
            break
    return distractors


async def get_level_up_problems(
    db: AsyncSession,
    user: User,
) -> LevelUpProblemsOut:
    """JLPT 형식 20문제 샘플링 후 HMAC 토큰과 함께 반환.

    구성 (현재 레벨 기준):
    - MCQ_MEANING × 5  (vocabulary)
    - MCQ_READING × 3  (vocabulary)
    - MCQ_CONTEXT × 3  (vocabulary)
    - MCQ_SYNONYM × 2  (vocabulary)
    - MCQ_GRAMMAR × 5  (grammar, 없으면 MCQ_MEANING 보충)
    - FILL_BLANK × 2   (vocabulary)
    """
    eligibility = await check_eligibility(db, user)
    if not eligibility.eligible:
        raise LevelUpError("응시 자격이 없습니다.", code="not_eligible")

    level = user.level

    # 유형별 문제 수집
    fetches: list[tuple[ProblemType, str, int]] = [
        (ProblemType.MCQ_MEANING, "vocabulary", 5),
        (ProblemType.MCQ_READING, "vocabulary", 3),
        (ProblemType.MCQ_CONTEXT, "vocabulary", 3),
        (ProblemType.MCQ_SYNONYM, "vocabulary", 2),
        (ProblemType.FILL_BLANK, "vocabulary", 2),
    ]
    all_problems: list[Problem] = []
    for ptype, kind, limit in fetches:
        probs = await _fetch_problems(db, level=level, problem_type=ptype, kind=kind, limit=limit)
        all_problems.extend(probs)

    # MCQ_GRAMMAR (grammar kind) — 없으면 MCQ_MEANING 보충
    if level in _GRAMMAR_LEVELS:
        grammar_probs = await _fetch_problems(
            db, level=level, problem_type=ProblemType.MCQ_GRAMMAR, kind="grammar", limit=5
        )
        if grammar_probs:
            all_problems.extend(grammar_probs)
        else:
            fill = await _fetch_problems(
                db, level=level, problem_type=ProblemType.MCQ_MEANING, kind="vocabulary", limit=5
            )
            all_problems.extend(fill)
    else:
        fill = await _fetch_problems(
            db, level=level, problem_type=ProblemType.MCQ_MEANING, kind="vocabulary", limit=5
        )
        all_problems.extend(fill)

    # 중복 제거
    seen_ids: set[UUID] = set()
    unique: list[Problem] = []
    for p in all_problems:
        if p.id not in seen_ids:
            seen_ids.add(p.id)
            unique.append(p)

    if not unique:
        raise LevelUpError("레벨업 시험용 콘텐츠가 부족합니다.", code="insufficient_content")

    random.shuffle(unique)

    problem_ids = [str(p.id) for p in unique]
    token = _sign_token(str(user.id), problem_ids)

    problems_out: list[LevelUpProblemOut] = []
    for p in unique:
        distractors = await _build_exam_distractors(db, p, level)
        problems_out.append(
            LevelUpProblemOut(
                problem_id=p.id,
                content_item_id=p.content_item_id,
                problem_type=p.type.value,
                prompt=p.prompt,
                answer=p.answer,
                distractors=distractors,
                tags=p.tags,
            )
        )

    return LevelUpProblemsOut(
        problems=problems_out,
        total=len(problems_out),
        level_up_token=token,
        from_level=level,
        to_level=eligibility.next_level or level,
    )


async def submit_level_up(
    db: AsyncSession,
    *,
    user: User,
    payload: LevelUpSubmitIn,
) -> LevelUpResultOut:
    """토큰 검증 → 채점(70% 기준) → LevelUpRecord 기록 → 합격 시 레벨 승급."""
    # 토큰 검증 — PlacementError 재사용
    try:
        allowed_ids = _verify_token(payload.level_up_token, str(user.id))
    except PlacementError as exc:
        raise LevelUpError(str(exc), code=exc.code) from exc

    submitted_ids = set(payload.answers.keys())
    if not submitted_ids.issubset(allowed_ids):
        raise LevelUpError("출제되지 않은 문제 ID가 포함되어 있습니다.", code="invalid_answers")
    if not submitted_ids:
        raise LevelUpError("answers가 비어 있습니다.", code="invalid_answers")

    # 미제출 문제 오답 처리
    complete_answers: dict[str, bool] = {pid: False for pid in allowed_ids}
    complete_answers.update(dict(payload.answers))

    total = len(complete_answers)
    correct = sum(1 for v in complete_answers.values() if v)
    score = correct / total if total > 0 else 0.0
    passed = score >= _PASS_THRESHOLD

    next_lvl = _next_level(user.level)
    from_level = user.level
    to_level = next_lvl or user.level

    # 기록 저장
    record = LevelUpRecord(
        user_id=user.id,
        from_level=from_level,
        to_level=to_level,
        passed=passed,
        score=score,
    )
    db.add(record)

    if passed and next_lvl:
        await user_repo.update_level(db, user=user, level=next_lvl)
        logger.info(
            "레벨업 성공: user=%s %s → %s (%.1f%%)", user.id, from_level, next_lvl, score * 100
        )
    else:
        logger.info("레벨업 실패: user=%s level=%s score=%.1f%%", user.id, from_level, score * 100)

    await db.commit()

    return LevelUpResultOut(
        passed=passed,
        score=score,
        correct=correct,
        total=total,
        from_level=from_level,
        to_level=to_level if passed else from_level,
        message="합격입니다! 다음 레벨로 승급했습니다."
        if passed
        else f"불합격입니다. 정답률 {score:.0%}. 7일 후 재응시 가능합니다.",
    )
