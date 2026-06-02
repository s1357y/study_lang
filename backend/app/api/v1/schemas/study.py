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
