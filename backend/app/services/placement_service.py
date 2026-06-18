"""배치 시험 서비스 — 출제·채점·레벨 배정을 담당한다.

보안:
- GET /placement/problems 응답 시 HMAC-서명 placement_token 발급
- POST /placement/submit 에서 토큰을 검증해 임의 problem_id 위조를 방지
- token 페이로드: {uid, pids(sorted), exp} 를 JSON 직렬화 후 HMAC-SHA256 서명

흐름:
- get_placement_problems: 레벨별 3문제 샘플링 → 셔플 → token 발급
- submit_placement: token 검증 → 채점 → user 레벨 갱신 → placement_done=True
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import random
from dataclasses import dataclass, field
from time import time
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.placement import (
    PlacementProblemOut,
    PlacementProblemsOut,
    PlacementResultOut,
    PlacementSubmitIn,
)
from app.core.config import settings
from app.core.logging import get_logger
from app.models.problem import Problem, ProblemType
from app.models.user import User
from app.repositories import content_repo, user_repo

logger = get_logger(__name__)

_LEVELS = ["BEGINNER", "ELEMENTARY", "INTERMEDIATE", "ADVANCED"]
_PASS_THRESHOLD = 2 / 3
_PROBLEMS_PER_LEVEL = 5  # 총 20문제 (레벨 4개 × 5문제)
_TOKEN_TTL_SEC = 1800  # 30분
# grammar 시드가 존재하는 레벨 — BEGINNER·ADVANCED는 MCQ_MEANING으로 대체
_GRAMMAR_LEVELS = frozenset({"ELEMENTARY", "INTERMEDIATE"})


class PlacementError(Exception):
    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass
class _PlacementProblem:
    problem: Problem
    level: str
    distractors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# placement_token 서명/검증 (stateless HMAC)
# ---------------------------------------------------------------------------


def _sign_token(user_id: str, problem_ids: list[str]) -> str:
    exp = int(time()) + _TOKEN_TTL_SEC
    payload = json.dumps({"uid": user_id, "pids": sorted(problem_ids), "exp": exp})
    payload_b64 = base64.urlsafe_b64encode(payload.encode()).decode()
    sig = hmac.new(settings.jwt_secret.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{sig}"


def _verify_token(token: str, user_id: str) -> set[str]:
    """서명 검증 후 허용된 problem_ids set 반환. 실패 시 PlacementError."""
    try:
        payload_b64, sig = token.rsplit(".", 1)
    except ValueError as exc:
        raise PlacementError("잘못된 토큰 형식", code="invalid_token") from exc

    expected = hmac.new(
        settings.jwt_secret.encode(), payload_b64.encode(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(sig, expected):
        raise PlacementError("토큰 서명 불일치", code="invalid_token")

    try:
        data = json.loads(base64.urlsafe_b64decode(payload_b64.encode()))
    except Exception as exc:
        raise PlacementError("토큰 디코딩 실패", code="invalid_token") from exc

    if data.get("uid") != user_id:
        raise PlacementError("토큰 사용자 불일치", code="invalid_token")
    if int(time()) > data.get("exp", 0):
        raise PlacementError("토큰 만료", code="token_expired")

    return set(data["pids"])


# ---------------------------------------------------------------------------
# 레벨 결정 로직
# ---------------------------------------------------------------------------


def compute_level(
    answers: dict[str, bool],
    problem_level_map: dict[str, str],
    sampled_level_set: set[str],
) -> str:
    """실제 출제된 레벨만 채점 대상으로 삼아 가장 높은 합격 레벨 반환."""
    for level in reversed(_LEVELS):
        if level not in sampled_level_set:
            continue
        level_answers = [v for pid, v in answers.items() if problem_level_map.get(pid) == level]
        if not level_answers:
            continue
        if sum(level_answers) / len(level_answers) >= _PASS_THRESHOLD:
            return level
    return "BEGINNER"


# ---------------------------------------------------------------------------
# 공개 API
# ---------------------------------------------------------------------------


async def _build_placement_distractors(
    db: AsyncSession,
    problem: Problem,
    level: str,
) -> list[str]:
    """배치 시험 문제의 오답 선택지 구성.

    선저장 유형(MCQ_GRAMMAR·MCQ_CONTEXT·MCQ_SYNONYM)은 JSONB에서 직접 읽고,
    동적 유형(MCQ_MEANING·MCQ_READING)은 같은 레벨 풀에서 추출한다.
    """
    pre_stored = {ProblemType.MCQ_GRAMMAR, ProblemType.MCQ_CONTEXT, ProblemType.MCQ_SYNONYM}
    if problem.type in pre_stored:
        return (problem.distractors or {}).get("options", [])

    # MCQ_MEANING 선저장 distractors 우선 — pool 쿼리 불필요
    if problem.type == ProblemType.MCQ_MEANING and problem.distractors:
        return (problem.distractors or {}).get("options", [])

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


async def get_placement_problems(
    db: AsyncSession,
    *,
    user: User,
    language: str = "ja",
) -> PlacementProblemsOut:
    """레벨별 5문제(혼합 유형) 샘플링 후 셔플하여 placement_token 과 함께 반환.

    구성 (레벨당 5문제, 총 20문제):
    - MCQ_MEANING × 2  (vocabulary)
    - MCQ_READING × 1  (vocabulary, 한자 단어 우선)
    - MCQ_GRAMMAR × 1  (grammar, ELEMENTARY·INTERMEDIATE만; 없으면 MCQ_MEANING 1개 보충)
    - MCQ_CONTEXT × 1  (vocabulary; 없으면 MCQ_SYNONYM, 없으면 MCQ_MEANING 1개 보충)
    """
    placement_problems: list[_PlacementProblem] = []
    sampled_levels: set[str] = set()

    for level in _LEVELS:
        level_problems: list[Problem] = []

        # 1) MCQ_MEANING × 2
        meaning_probs = await content_repo.get_problems_for_placement(
            db,
            language=language,
            level=level,
            problem_type=ProblemType.MCQ_MEANING,
            kind="vocabulary",
            limit=2,
        )
        level_problems.extend(meaning_probs)

        # 2) MCQ_READING × 1
        reading_probs = await content_repo.get_problems_for_placement(
            db,
            language=language,
            level=level,
            problem_type=ProblemType.MCQ_READING,
            kind="vocabulary",
            limit=1,
        )
        level_problems.extend(reading_probs)

        # 3) MCQ_GRAMMAR × 1 (grammar 시드 있는 레벨만; 없으면 MCQ_MEANING 보충)
        if level in _GRAMMAR_LEVELS:
            grammar_probs = await content_repo.get_problems_for_placement(
                db,
                language=language,
                level=level,
                problem_type=ProblemType.MCQ_GRAMMAR,
                kind="grammar",
                limit=1,
            )
            if grammar_probs:
                level_problems.extend(grammar_probs)
            else:
                fill = await content_repo.get_problems_for_placement(
                    db,
                    language=language,
                    level=level,
                    problem_type=ProblemType.MCQ_MEANING,
                    kind="vocabulary",
                    limit=1,
                )
                level_problems.extend(fill)
        else:
            # BEGINNER·ADVANCED: grammar 없으므로 MCQ_MEANING 1개 보충
            fill = await content_repo.get_problems_for_placement(
                db,
                language=language,
                level=level,
                problem_type=ProblemType.MCQ_MEANING,
                kind="vocabulary",
                limit=1,
            )
            level_problems.extend(fill)

        # 4) MCQ_CONTEXT × 1 (없으면 MCQ_SYNONYM, 없으면 MCQ_MEANING 보충)
        ctx_probs = await content_repo.get_problems_for_placement(
            db,
            language=language,
            level=level,
            problem_type=ProblemType.MCQ_CONTEXT,
            kind="vocabulary",
            limit=1,
        )
        if ctx_probs:
            level_problems.extend(ctx_probs)
        else:
            syn_probs = await content_repo.get_problems_for_placement(
                db,
                language=language,
                level=level,
                problem_type=ProblemType.MCQ_SYNONYM,
                kind="vocabulary",
                limit=1,
            )
            if syn_probs:
                level_problems.extend(syn_probs)
            else:
                fill = await content_repo.get_problems_for_placement(
                    db,
                    language=language,
                    level=level,
                    problem_type=ProblemType.MCQ_MEANING,
                    kind="vocabulary",
                    limit=1,
                )
                level_problems.extend(fill)

        if not level_problems:
            logger.info("배치 시험: %s 레벨 콘텐츠 없음 — 건너뜀", level)
            continue

        # 중복 제거 (id 기준)
        seen_ids: set[UUID] = set()
        unique_problems: list[Problem] = []
        for p in level_problems:
            if p.id not in seen_ids:
                seen_ids.add(p.id)
                unique_problems.append(p)

        for p in unique_problems:
            distractors = await _build_placement_distractors(db, p, level)
            placement_problems.append(
                _PlacementProblem(problem=p, level=level, distractors=distractors)
            )
        sampled_levels.add(level)

    if not placement_problems:
        raise PlacementError(
            "배치 시험용 콘텐츠가 부족합니다. 먼저 시드 데이터를 추가하세요.",
            code="insufficient_content",
        )

    random.shuffle(placement_problems)

    problem_ids = [str(pp.problem.id) for pp in placement_problems]
    token = _sign_token(str(user.id), problem_ids)

    problems_out = [
        PlacementProblemOut(
            problem_id=pp.problem.id,
            content_item_id=pp.problem.content_item_id,
            problem_type=pp.problem.type.value,
            prompt=pp.problem.prompt,
            answer=pp.problem.answer,
            distractors=pp.distractors,
            tags=pp.problem.tags,
        )
        for pp in placement_problems
    ]
    return PlacementProblemsOut(
        problems=problems_out,
        total=len(problems_out),
        placement_token=token,
    )


async def submit_placement(
    db: AsyncSession,
    *,
    user: User,
    payload: PlacementSubmitIn,
) -> PlacementResultOut:
    """토큰 검증 → 채점 → 레벨 갱신 → placement_done 기록 → commit."""
    # 1. placement_token 검증 — 허용된 problem_ids set 복원
    allowed_ids = _verify_token(payload.placement_token, str(user.id))

    # 2. 제출 키가 허용 집합의 부분집합인지 확인 (위조 방지)
    submitted_ids = set(payload.answers.keys())
    if not submitted_ids.issubset(allowed_ids):
        raise PlacementError("출제되지 않은 문제 ID가 포함되어 있습니다.", code="invalid_answers")

    if not submitted_ids:
        raise PlacementError("answers가 비어 있습니다.", code="invalid_answers")

    # 3. 토큰의 전체 출제 문제로 레벨 맵 구성 — 미제출 문제는 오답(False) 처리
    # submitted_ids 만으로 구성하면 어려운 문제를 생략해 상위 레벨을 조작할 수 있음
    all_token_ids = [UUID(pid) for pid in allowed_ids]
    problems = await content_repo.get_problems_by_ids(db, all_token_ids)
    citem_map = await content_repo.get_items_by_ids(db, [p.content_item_id for p in problems])

    problem_level_map: dict[str, str] = {}
    for p in problems:
        ci = citem_map.get(p.content_item_id)
        if ci:
            problem_level_map[str(p.id)] = ci.level

    # sampled_level_set: 토큰에 포함된 전체 출제 레벨 (미제출 레벨도 포함)
    sampled_level_set: set[str] = set(problem_level_map.values())

    # 미제출 문제는 오답으로 간주해 완전한 답안 구성
    complete_answers: dict[str, bool] = {pid: False for pid in allowed_ids}
    complete_answers.update(dict(payload.answers))

    # 4. 레벨 결정
    assigned_level = compute_level(complete_answers, problem_level_map, sampled_level_set)
    logger.info("배치 시험 결과: user=%s level=%s", user.id, assigned_level)

    # 5. 유저 레벨 갱신 + 완료 기록
    await user_repo.update_level(db, user=user, level=assigned_level)
    await user_repo.mark_placement_done(db, user=user)
    await db.commit()

    return PlacementResultOut.from_level(assigned_level)


async def skip_placement(db: AsyncSession, *, user: User) -> None:
    """배치 시험 건너뛰기 — placement_done=True 만 기록, 레벨 유지."""
    await user_repo.mark_placement_done(db, user=user)
    await db.commit()
