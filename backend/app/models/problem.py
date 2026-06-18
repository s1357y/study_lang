"""Problem 모델 — ContentItem 에서 파생된 실제 출제 문제.

설계 의도:
- 하나의 ContentItem 에서 여러 유형의 문제 생성 가능
- distractors(JSONB) 에 오답 선택지를 유연하게 저장
- tags 는 ContentItem.tags 를 복사해 AttemptLog 집계에 활용
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String, Text, TypeDecorator
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.content_item import ContentItem


class ProblemType(StrEnum):
    """출제 가능한 문제 유형.

    TRANSLATION 의 방향(ko_to_jp / jp_to_ko)은 Problem.meta["direction"] 로 저장.
    LISTENING 은 Phase 5+ 에서 TTS 인프라 준비 후 활성화.
    신규 MCQ 유형(MCQ_GRAMMAR·MCQ_CONTEXT·MCQ_SYNONYM)은 distractors 가 생성 시 선저장됨.
    """

    MCQ_MEANING = "mcq_meaning"  # 일본어 단어 → 한국어 의미 고르기
    MCQ_READING = "mcq_reading"  # 漢字 → 히라가나 읽기 고르기
    FILL_BLANK = "fill_blank"  # 예문 빈칸에 단어 채우기
    TRANSLATION = "translation"  # 한국어 ↔ 일본어 번역 (방향: meta.direction)
    LISTENING = "listening"  # 오디오 듣고 의미/읽기 고르기
    MCQ_GRAMMAR = "mcq_grammar"  # 문장 빈칸에 맞는 문법 표현 선택 (JLPT 文法1)
    MCQ_CONTEXT = "mcq_context"  # 문맥에서 밑줄 단어의 의미 선택 (JLPT 文脈規定)
    MCQ_SYNONYM = "mcq_synonym"  # 유의어·바꿔쓰기 선택 (JLPT 言い換え類義)


class ProblemTypeDecorator(TypeDecorator):
    """DB String(20) ↔ ProblemType enum 자동 변환."""

    impl = String(20)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        # enum 값 → DB 저장 문자열
        if isinstance(value, ProblemType):
            return value.value
        return value

    def process_result_value(self, value, dialect):
        # DB 문자열 → enum 인스턴스
        if value is not None:
            return ProblemType(value)
        return value


class Problem(Base):
    __tablename__ = "problem"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)

    # 원본 ContentItem — 삭제 시 문제도 함께 삭제
    content_item_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("content_item.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # 문제 유형 — ProblemTypeDecorator 가 DB str ↔ ProblemType enum 자동 변환
    type: Mapped[ProblemType] = mapped_column(ProblemTypeDecorator, nullable=False)

    # 문제 본문
    prompt: Mapped[str] = mapped_column(Text, nullable=False)

    # 정답
    answer: Mapped[str] = mapped_column(Text, nullable=False)

    # 오답 선택지 {"options": ["선택1", "선택2", "선택3"]} 형태
    distractors: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    # ContentItem.tags 를 복사 — AttemptLog 집계 시 조인 없이 사용
    tags: Mapped[list[str]] = mapped_column(ARRAY(String(100)), nullable=False)

    # 추가 메타 (생성 파라미터, 모델 버전 등 기록용)
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    content_item: Mapped[ContentItem] = relationship("ContentItem", back_populates="problems")
