"""Motivation 도메인 Pydantic 스키마."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, computed_field


class MotivationOut(BaseModel):
    streak_days: int
    xp: int
    level: int
    weekly_goal_minutes: int
    weekly_progress_seconds: int
    weekly_period_start: date | None

    # 프론트 편의 — 초→분 환산 (소수점 버림)
    @computed_field  # type: ignore[prop-decorator]
    @property
    def weekly_progress_minutes(self) -> int:
        return self.weekly_progress_seconds // 60

    model_config = {"from_attributes": True}
