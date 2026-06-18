"""ContentItem / Problem 테이블 접근.

서비스 계층(content_service, generation_service, study_service)이 이 함수들을 조합한다.
"""

from __future__ import annotations

import random
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content_item import ContentItem
from app.models.problem import Problem, ProblemType


async def create(
    db: AsyncSession,
    *,
    language: str,
    level: str,
    kind: str,
    tags: list[str],
    payload: dict[str, Any],
    source: str = "llm",
    quality_score: float | None = None,
    generated_at: datetime | None = None,
) -> ContentItem:
    # ContentItem 저장 — commit 은 서비스 계층에서 일괄 처리
    item = ContentItem(
        language=language,
        level=level,
        kind=kind,
        tags=tags,
        payload=payload,
        source=source,
        quality_score=quality_score,
        generated_at=generated_at,
    )
    db.add(item)
    await db.flush()
    return item


async def create_problem(
    db: AsyncSession,
    *,
    content_item_id: UUID,
    problem_type: ProblemType,
    prompt: str,
    answer: str,
    distractors: dict[str, Any] | None = None,
    tags: list[str],
    meta: dict[str, Any] | None = None,
) -> Problem:
    problem = Problem(
        content_item_id=content_item_id,
        type=problem_type,
        prompt=prompt,
        answer=answer,
        distractors=distractors,
        tags=tags,
        meta=meta or {},
    )
    db.add(problem)
    await db.flush()
    return problem


async def get_pool(
    db: AsyncSession,
    *,
    language: str = "ja",
    level: str,
    kind: str = "vocabulary",
    filter_tags: list[str] | None = None,
    exclude_ids: list[UUID] | None = None,
    limit: int = 10,
) -> list[ContentItem]:
    # 조건에 맞는 콘텐츠 풀 조회 — created_at 오름차순 (먼저 생성된 것 우선)
    stmt = (
        select(ContentItem)
        .where(
            ContentItem.language == language, ContentItem.level == level, ContentItem.kind == kind
        )
        .order_by(ContentItem.created_at.asc())
        .limit(limit)
    )

    # 약점 태그 필터 — content_item.tags && filter_tags (교집합이 있는 항목)
    if filter_tags:
        stmt = stmt.where(ContentItem.tags.overlap(filter_tags))

    # 이미 학습한 항목 제외 (Phase 4 에서 ReviewRecord 기반으로 고도화)
    if exclude_ids:
        stmt = stmt.where(ContentItem.id.notin_(exclude_ids))

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_seeds(
    db: AsyncSession,
    *,
    language: str = "ja",
    level: str,
    kind: str = "vocabulary",
) -> list[ContentItem]:
    # source="seed" 인 기존 seed 항목 조회 — 중복 삽입 방지용
    stmt = select(ContentItem).where(
        ContentItem.language == language,
        ContentItem.level == level,
        ContentItem.kind == kind,
        ContentItem.source == "seed",
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def count_pool(
    db: AsyncSession,
    *,
    language: str = "ja",
    level: str | None = None,
) -> dict[str, int]:
    # 레벨별 콘텐츠 수 집계 — 워커의 임계치 판단과 풀 통계에 사용
    stmt = select(ContentItem.level, func.count().label("cnt")).where(
        ContentItem.language == language
    )
    if level:
        stmt = stmt.where(ContentItem.level == level)
    stmt = stmt.group_by(ContentItem.level)

    result = await db.execute(stmt)
    return {row.level: row.cnt for row in result.all()}


# ---------------------------------------------------------------------------
# study_service 에서 필요한 조회 함수
# ---------------------------------------------------------------------------


async def get_problem_by_id(db: AsyncSession, problem_id: UUID) -> Problem | None:
    # PK 직접 조회 — 시도 제출 시 문제 존재 여부 확인용
    return await db.get(Problem, problem_id)


async def get_random_problem_per_item(
    db: AsyncSession,
    content_item_ids: list[UUID],
) -> dict[UUID, Problem]:
    """ContentItem당 가용 Problem 중 랜덤 1개 선택 — 세션마다 문제 유형 다양성 확보."""
    if not content_item_ids:
        return {}
    stmt = select(Problem).where(Problem.content_item_id.in_(content_item_ids))
    result = await db.execute(stmt)
    all_problems = result.scalars().all()

    # content_item_id별로 그룹핑
    groups: dict[UUID, list[Problem]] = {}
    for p in all_problems:
        groups.setdefault(p.content_item_id, []).append(p)

    # 각 그룹에서 랜덤 1개 선택
    return {cid: random.choice(problems) for cid, problems in groups.items()}


async def get_representative_problems(
    db: AsyncSession,
    content_item_ids: list[UUID],
) -> dict[UUID, Problem]:
    """ContentItem 당 MCQ_MEANING 우선 대표 Problem 하나를 반환.

    하위 호환 별칭 — 신규 코드는 get_random_problem_per_item() 사용 권장.
    """
    if not content_item_ids:
        return {}
    stmt = select(Problem).where(Problem.content_item_id.in_(content_item_ids))
    result = await db.execute(stmt)
    all_problems = result.scalars().all()

    best: dict[UUID, Problem] = {}
    for p in all_problems:
        cid = p.content_item_id
        if cid not in best:
            best[cid] = p
        elif best[cid].type != ProblemType.MCQ_MEANING and p.type == ProblemType.MCQ_MEANING:
            best[cid] = p
    return best


async def get_problems_by_ids(
    db: AsyncSession,
    problem_ids: list[UUID],
) -> list[Problem]:
    # 기존 세션 재로드 시 planned_problem_ids 로 Problem 일괄 조회
    if not problem_ids:
        return []
    stmt = select(Problem).where(Problem.id.in_(problem_ids))
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_items_by_ids(
    db: AsyncSession,
    item_ids: list[UUID],
) -> dict[UUID, ContentItem]:
    # content_item_id 목록으로 ContentItem 일괄 조회
    if not item_ids:
        return {}
    stmt = select(ContentItem).where(ContentItem.id.in_(item_ids))
    result = await db.execute(stmt)
    return {ci.id: ci for ci in result.scalars().all()}


async def get_problems_for_placement(
    db: AsyncSession,
    *,
    language: str = "ja",
    level: str,
    problem_type: ProblemType = ProblemType.MCQ_MEANING,
    kind: str = "vocabulary",
    limit: int = 3,
) -> list[Problem]:
    # Problem JOIN ContentItem 으로 레벨·kind 필터 + random 샘플링
    stmt = (
        select(Problem)
        .join(ContentItem, Problem.content_item_id == ContentItem.id)
        .where(
            ContentItem.language == language,
            ContentItem.level == level,
            ContentItem.kind == kind,
            Problem.type == problem_type,
        )
        .order_by(func.random())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_items_by_level_excluding(
    db: AsyncSession,
    *,
    level: str,
    exclude_id: UUID,
    kind: str = "vocabulary",
    limit: int = 20,
) -> list[ContentItem]:
    # MCQ 오답 선택지 후보 — 같은 레벨·kind 에서 해당 아이템만 제외
    stmt = (
        select(ContentItem)
        .where(
            ContentItem.level == level,
            ContentItem.kind == kind,
            ContentItem.id != exclude_id,
        )
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
