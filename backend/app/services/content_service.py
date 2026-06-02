"""콘텐츠 풀 관리 — 기존 풀 우선 조회 → 부족 시 LLM 생성 → 실패 시 seed 폴백.

우선순위:
1. DB 풀에서 조건에 맞는 콘텐츠 조회 (가장 빠름, 비용 없음)
2. 풀 부족 시 generation_service 를 통해 on-demand LLM 생성
3. LLM 실패 시 내장 seed 데이터를 DB 에 저장 후 반환 (항상 동작 보장)

seed 데이터는 JLPT N5 수준 어휘 10개로, Ollama 없이도 기본 동작이 가능하다.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.llm.client import LLMError
from app.models.content_item import ContentItem
from app.repositories import content_repo
from app.services import generation_service

logger = get_logger(__name__)

# JLPT N5 기본 어휘 seed — Ollama 없이도 최소 동작 보장
_SEED_VOCABULARY: list[dict[str, Any]] = [
    {"word": "水", "reading": "みず", "meaning_ko": "물", "example_ja": "水を飲みます。", "example_ko": "물을 마십니다.", "tags": ["noun", "N5"]},
    {"word": "食べる", "reading": "たべる", "meaning_ko": "먹다", "example_ja": "昼ご飯を食べます。", "example_ko": "점심을 먹습니다.", "tags": ["verb", "ichidan", "N5"]},
    {"word": "学校", "reading": "がっこう", "meaning_ko": "학교", "example_ja": "学校へ行きます。", "example_ko": "학교에 갑니다.", "tags": ["noun", "N5"]},
    {"word": "友達", "reading": "ともだち", "meaning_ko": "친구", "example_ja": "友達と遊びます。", "example_ko": "친구와 놉니다.", "tags": ["noun", "N5"]},
    {"word": "先生", "reading": "せんせい", "meaning_ko": "선생님", "example_ja": "先生に質問します。", "example_ko": "선생님께 질문합니다.", "tags": ["noun", "N5"]},
    {"word": "時間", "reading": "じかん", "meaning_ko": "시간", "example_ja": "時間がありません。", "example_ko": "시간이 없습니다.", "tags": ["noun", "N5"]},
    {"word": "電車", "reading": "でんしゃ", "meaning_ko": "전철", "example_ja": "電車で行きます。", "example_ko": "전철로 갑니다.", "tags": ["noun", "N5"]},
    {"word": "買う", "reading": "かう", "meaning_ko": "사다", "example_ja": "本を買います。", "example_ko": "책을 삽니다.", "tags": ["verb", "godan", "N5"]},
    {"word": "今日", "reading": "きょう", "meaning_ko": "오늘", "example_ja": "今日は月曜日です。", "example_ko": "오늘은 월요일입니다.", "tags": ["noun", "time", "N5"]},
    {"word": "大きい", "reading": "おおきい", "meaning_ko": "크다", "example_ja": "大きい犬がいます。", "example_ko": "큰 개가 있습니다.", "tags": ["adjective", "i-adj", "N5"]},
]


async def _save_seed_items(
    db: AsyncSession,
    *,
    level: str,
    needed: int,
) -> list[ContentItem]:
    """부족한 seed 어휘를 DB 에 저장하고 seed ContentItem 목록을 반환한다.

    이미 저장된 항목은 스킵하여 중복 삽입을 방지한다.
    """
    # 기존 seed 항목 조회 — 중복 삽입 방지
    existing = await content_repo.get_seeds(db, language="ja", level=level)
    existing_words = {item.payload.get("word") for item in existing}

    # 없는 항목만 삽입
    saved: list[ContentItem] = []
    now = datetime.now(timezone.utc)
    for vocab in _SEED_VOCABULARY:
        if vocab["word"] in existing_words:
            continue
        item = await content_repo.create(
            db,
            language="ja",
            level=level,
            kind="vocabulary",
            tags=vocab["tags"],
            payload={k: v for k, v in vocab.items() if k != "tags"},
            source="seed",
            quality_score=0.8,
            generated_at=now,
        )
        saved.append(item)

    if saved:
        await db.commit()
        logger.info("seed 어휘 %d개 DB 저장 완료 (level=%s)", len(saved), level)

    return (existing + saved)[:needed]


async def get_or_generate(
    db: AsyncSession,
    *,
    level: str = "BEGINNER",
    tags: list[str],
    count: int = 5,
    exclude_ids: list[UUID] | None = None,
) -> list[ContentItem]:
    """콘텐츠를 반환한다. 풀 부족 → LLM 생성 → seed 폴백 순서로 시도."""

    # 1) 기존 풀에서 우선 조회
    pool = await content_repo.get_pool(
        db,
        level=level,
        filter_tags=tags or None,
        exclude_ids=exclude_ids,
        limit=count,
    )
    if len(pool) >= count:
        return pool

    # 2) 풀이 부족하면 LLM 으로 부족분 생성
    needed = count - len(pool)
    try:
        generated = await generation_service.generate_vocabulary(
            db, level=level, tags=tags, count=needed
        )
        pool.extend(generated)
    except (LLMError, RuntimeError) as exc:
        logger.warning("LLM 생성 실패, seed 폴백: %s", exc)

    # 3) 여전히 부족하면 seed 를 DB 에 저장 후 반환
    if len(pool) < count:
        seed_items = await _save_seed_items(db, level=level, needed=count - len(pool))
        pool.extend(seed_items)

    return pool


async def get_pool_stats(db: AsyncSession, *, language: str = "ja") -> dict[str, int]:
    # 레벨별 콘텐츠 수 — 워커가 임계치 판단에 사용
    return await content_repo.count_pool(db, language=language)
