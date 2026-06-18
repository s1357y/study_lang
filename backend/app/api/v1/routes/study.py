"""Study 라우트 — SRS 학습 세션, 시도 제출, 통계 조회, 복습.

엔드포인트:
- POST /sessions/today          : 오늘 학습 세션 생성 또는 기존 세션 반환
- GET  /sessions                : 최근 세션 요약 목록
- GET  /sessions/{date}/review  : 날짜별 완료 문제 복습 카드
- POST /attempts                : 문제 풀이 결과 제출 (SRS 갱신 + 약점 기록)
- GET  /stats                   : 오늘 복습 수/신규 수/약점 태그 조회
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import current_user, get_db
from app.api.v1.schemas.study import (
    AttemptCreate,
    AttemptOut,
    ProblemOut,
    ReviewItemOut,
    SessionSummaryOut,
    StudySessionOut,
    StudyStatsOut,
)
from app.models.user import User
from app.services import study_service
from app.services.study_service import StudyError

router = APIRouter()


def _study_error_to_http(exc: StudyError) -> HTTPException:
    # 도메인 코드 → HTTP 상태 매핑
    if exc.code in ("not_found", "session_not_found"):
        return HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc))
    if exc.code == "invalid_date":
        return HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if exc.code == "no_more_content":
        return HTTPException(status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/sessions/today", response_model=StudySessionOut)
async def get_or_create_today_session(
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> StudySessionOut:
    session, problems = await study_service.build_today_session(db, user)

    problems_out = [
        ProblemOut(
            problem_id=pw.problem.id,
            content_item_id=pw.problem.content_item_id,
            problem_type=pw.problem.type.value,
            prompt=pw.problem.prompt,
            answer=pw.problem.answer,
            distractors=pw.distractors,
            tags=pw.problem.tags,
        )
        for pw in problems
    ]
    return StudySessionOut(
        id=session.id,
        date=session.date,
        problems=problems_out,
        completed_count=len(session.completed_problem_ids),
        total_count=len(session.planned_problem_ids),
        started_at=session.started_at,
    )


@router.post("/sessions/today/extend", response_model=StudySessionOut)
async def extend_today_session(
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> StudySessionOut:
    """오늘 세션에 추가 문제 10개를 붙인다. 풀 소진 시 LLM 생성 폴백."""
    try:
        session, problems = await study_service.extend_today_session(db, user)
    except StudyError as exc:
        raise _study_error_to_http(exc) from exc

    problems_out = [
        ProblemOut(
            problem_id=pw.problem.id,
            content_item_id=pw.problem.content_item_id,
            problem_type=pw.problem.type.value,
            prompt=pw.problem.prompt,
            answer=pw.problem.answer,
            distractors=pw.distractors,
            tags=pw.problem.tags,
        )
        for pw in problems
    ]
    return StudySessionOut(
        id=session.id,
        date=session.date,
        problems=problems_out,
        completed_count=len(session.completed_problem_ids),
        total_count=len(session.planned_problem_ids),
        started_at=session.started_at,
    )


@router.post("/attempts", response_model=AttemptOut, status_code=status.HTTP_201_CREATED)
async def submit_attempt(
    body: AttemptCreate,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> AttemptOut:
    try:
        log, record = await study_service.record_attempt(
            db,
            user_id=user.id,
            problem_id=body.problem_id,
            content_item_id=body.content_item_id,
            correct=body.correct,
            response_time_ms=body.response_time_ms,
        )
    except StudyError as exc:
        raise _study_error_to_http(exc) from exc

    return AttemptOut(
        id=log.id,
        correct=log.correct,
        rating=log.rating,
        next_due_at=record.next_due_at,
        created_at=log.created_at,
    )


@router.get("/sessions", response_model=list[SessionSummaryOut])
async def get_recent_sessions(
    limit: Annotated[int, Query(ge=1, le=30)] = 7,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SessionSummaryOut]:
    return await study_service.get_recent_sessions(db, user_id=user.id, limit=limit)


@router.get("/sessions/{date_str}/review", response_model=list[ReviewItemOut])
async def get_session_review(
    date_str: Annotated[str, Path(pattern=r"^\d{4}-\d{2}-\d{2}$")],
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ReviewItemOut]:
    try:
        return await study_service.get_session_review(db, user_id=user.id, date_str=date_str)
    except StudyError as exc:
        raise _study_error_to_http(exc) from exc


@router.get("/stats", response_model=StudyStatsOut)
async def get_study_stats(
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> StudyStatsOut:
    due_today, new_available, weak_tags = await study_service.get_stats(db, user)
    return StudyStatsOut(
        due_today=due_today,
        new_available=new_available,
        weak_tags=weak_tags,
    )
