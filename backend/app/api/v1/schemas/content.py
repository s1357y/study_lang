"""콘텐츠 관련 API 스키마 (Pydantic).

라우트 요청/응답의 단일 출처.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    level: str = Field(default="BEGINNER", description="BEGINNER / ELEMENTARY / INTERMEDIATE / ADVANCED")
    tags: list[str] = Field(default_factory=list, description="약점 태그 (집중 생성에 반영)")
    count: int = Field(default=3, ge=1, le=10, description="생성할 콘텐츠 수")


class ContentItemResponse(BaseModel):
    id: UUID
    language: str
    level: str
    kind: str
    tags: list[str]
    payload: dict[str, Any]
    source: str
    quality_score: float | None
    created_at: datetime

    model_config = {"from_attributes": True}


class PoolStatsResponse(BaseModel):
    total: int
    by_level: dict[str, int]
