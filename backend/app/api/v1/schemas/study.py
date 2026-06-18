"""Study 도메인 Pydantic 스키마."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel


class AttemptCreate(BaseModel):
    problem_id: UUID
    content_item_id: UUID
    correct: bool
    response_time_ms: int


class AttemptOut(BaseModel):
    id: UUID
    correct: bool
    rating: str | None
    next_due_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class ProblemOut(BaseModel):
    problem_id: UUID
    content_item_id: UUID
    problem_type: str
    prompt: str
    answer: str
    distractors: list[str]
    tags: list[str]


class StudySessionOut(BaseModel):
    id: UUID
    date: date
    problems: list[ProblemOut]
    completed_count: int
    total_count: int
    started_at: datetime


class StudyStatsOut(BaseModel):
    due_today: int
    new_available: int
    weak_tags: list[str]


# ---------------------------------------------------------------------------
# 복습(Session Review) 스키마
# ---------------------------------------------------------------------------


class ContentItemPayload(BaseModel):
    # extra="allow" 로 미래 필드 추가에도 유연하게 대응
    # vocabulary 필드
    word: str | None = None
    reading: str | None = None
    meaning_ko: str | None = None
    example_ja: str | None = None
    example_ko: str | None = None
    # grammar 필드
    grammar_point: str | None = None
    pattern_ja: str | None = None
    usage_ko: str | None = None
    similar_patterns: list[str] | None = None
    wrong_patterns: list[str] | None = None

    model_config = {"extra": "allow"}


class ReviewItemOut(BaseModel):
    # distractors 제외 — 복습 화면 목적과 무관하므로 추가 DB 호출 없음
    problem_id: UUID
    content_item_id: UUID
    problem_type: str
    prompt: str
    answer: str
    tags: list[str]
    payload: ContentItemPayload
    my_correct: bool | None
    my_rating: str | None
    attempted_at: datetime | None


class SessionSummaryOut(BaseModel):
    id: UUID
    date: date
    completed_count: int
    total_count: int
    started_at: datetime
    finished_at: datetime | None

    model_config = {"from_attributes": True}
