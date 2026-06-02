"""ContentItem 모델 — LLM 또는 시드 데이터로 생성된 일본어 학습 콘텐츠.

설계 의도:
- payload(JSONB) 에 어휘/예문/해설 등 종류(kind)별 데이터를 유연하게 담는다
- tags(ARRAY) 로 약점 기반 필터링 및 SRS 연동
- source 로 llm/seed/manual 출처를 구분해 품질 관리
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Float, Index, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ContentItem(Base):
    __tablename__ = "content_item"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)

    # 대상 언어 — Phase 1 MVP 는 "ja"(일본어) 고정
    language: Mapped[str] = mapped_column(String(8), nullable=False, default="ja")

    # 난이도 — BEGINNER(N5) / ELEMENTARY(N4) / INTERMEDIATE(N3) / ADVANCED(N1-N2)
    level: Mapped[str] = mapped_column(String(20), nullable=False)

    # 콘텐츠 종류 — vocabulary / grammar / reading
    kind: Mapped[str] = mapped_column(String(20), nullable=False)

    # 약점 태그 (SRS 연동 + 프롬프트 주입용)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String(100)), nullable=False)

    # 종류별 구조화 데이터 (어휘: word/reading/meaning_ko/example_ja/example_ko 등)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    # 출처: llm (자동 생성) | seed (내장 데이터) | manual (수동 입력)
    source: Mapped[str] = mapped_column(String(10), nullable=False, default="llm")

    # 검증 통과 여부 등 기반의 품질 점수 (0.0 ~ 1.0)
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # LLM 생성 시각 (seed는 NULL)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # 이 ContentItem 으로 만들어진 문제들
    problems: Mapped[list["Problem"]] = relationship(
        "Problem", back_populates="content_item", cascade="all, delete-orphan"
    )

    __table_args__ = (
        # 언어/레벨/종류 기반 풀 조회의 핵심 인덱스
        Index("ix_content_language_level_kind", "language", "level", "kind"),
    )
