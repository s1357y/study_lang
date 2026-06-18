"""LLM 출력 구조 정의 (Pydantic).

Ollama 가 generate_json() 으로 반환하는 dict 를 이 스키마로 파싱한다.
프롬프트 템플릿(vocabulary_ja.j2 등)과 이 스키마는 항상 쌍으로 관리한다.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class VocabularyOutput(BaseModel):
    """어휘 생성 결과 단건."""

    word: str = Field(..., description="일본어 단어/표현")
    reading: str = Field(..., description="히라가나 읽기")
    meaning_ko: str = Field(..., description="한국어 의미")
    example_ja: str = Field(..., description="일본어 예문")
    example_ko: str = Field(..., description="한국어 번역")
    tags: list[str] = Field(default_factory=list, description="품사/JLPT 등 태그")
    synonyms: list[str] = Field(
        default_factory=list, description="MCQ_SYNONYM용 유의어 2~3개 (한국어)"
    )
    confusable_meanings: list[str] = Field(
        default_factory=list,
        description="MCQ_MEANING 오답용 헷갈리는 한국어 의미 3개 (같은 품사, 유사 의미 영역)",
    )


class VocabularyBatch(BaseModel):
    """어휘 생성 배치 응답 — 프롬프트 템플릿의 최상위 JSON 구조."""

    items: list[VocabularyOutput] = Field(default_factory=list)


class GrammarOutput(BaseModel):
    """문법 콘텐츠 생성 결과 단건."""

    grammar_point: str = Field(..., description="문법 포인트 표기 (예: 〜ので)")
    pattern_ja: str = Field(..., description="접속 패턴 (예: V普通形+ので)")
    meaning_ko: str = Field(..., description="한국어 의미")
    usage_ko: str = Field(..., description="사용법·뉘앙스 설명 (한국어)")
    example_ja: str = Field(..., description="문법 포인트가 포함된 일본어 예문")
    example_ko: str = Field(..., description="예문 한국어 번역")
    similar_patterns: list[str] = Field(default_factory=list, description="유사 문법 패턴")
    wrong_patterns: list[str] = Field(
        default_factory=list, description="오답 선택지용 혼동 패턴 (최소 3개)"
    )
    tags: list[str] = Field(default_factory=list, description="grammar/JLPT 등 태그")


class GrammarBatch(BaseModel):
    """문법 생성 배치 응답 — 프롬프트 템플릿의 최상위 JSON 구조."""

    items: list[GrammarOutput] = Field(default_factory=list)
