"""레벨업 시험 Pydantic 스키마."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class LevelUpEligibilityOut(BaseModel):
    eligible: bool
    studied_count: int
    required_count: int
    cooldown_until: datetime | None
    next_level: str | None


class LevelUpProblemOut(BaseModel):
    problem_id: UUID
    content_item_id: UUID
    problem_type: str
    prompt: str
    answer: str
    distractors: list[str]
    tags: list[str]


class LevelUpProblemsOut(BaseModel):
    problems: list[LevelUpProblemOut]
    total: int
    level_up_token: str
    from_level: str
    to_level: str


class LevelUpSubmitIn(BaseModel):
    level_up_token: str
    answers: dict[str, bool]


class LevelUpResultOut(BaseModel):
    passed: bool
    score: float
    correct: int
    total: int
    from_level: str
    to_level: str
    message: str
