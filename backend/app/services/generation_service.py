"""LLM 호출 오케스트레이션 — 프롬프트 렌더링 → Ollama 호출 → 검증 → DB 저장.

흐름:
1. Jinja2 템플릿으로 프롬프트 생성 (level + weak_tags 주입)
2. llm_client.generate_json() 으로 Ollama 호출
3. VocabularyBatch 파싱 + validate_vocabulary_output() 검증
4. 검증 통과 항목만 content_repo.create() 로 DB 저장
5. 생성된 ContentItem 목록 반환

이 모듈은 LLM 을 사용하는 유일한 서비스. 직접 httpx 호출 금지.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, TemplateNotFound
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.llm import client as llm_client
from app.llm.schemas import VocabularyBatch
from app.llm.validators import validate_vocabulary_output
from app.models.content_item import ContentItem
from app.models.problem import ProblemType
from app.repositories import content_repo

logger = get_logger(__name__)

# 프롬프트 템플릿 디렉토리 — 파일 위치 기준으로 절대 경로 구성
_PROMPTS_DIR = Path(__file__).parent.parent / "llm" / "prompts"
_jinja_env = Environment(loader=FileSystemLoader(str(_PROMPTS_DIR)), autoescape=False)

# CJK 한자 범위 — 복합어 경계 판단에 사용
_CJK_RE = re.compile(r"[一-鿿]")


def _find_standalone_word(word: str, text: str) -> int:
    """단독으로 쓰인 단어의 첫 번째 시작 인덱스를 반환한다.

    직전·직후 문자가 한자이면 복합어 내부로 간주하고 스킵.
    단독 일치가 없으면 -1 반환.
    """
    for m in re.finditer(re.escape(word), text):
        start, end = m.start(), m.end()
        before_ok = start == 0 or not _CJK_RE.match(text[start - 1])
        after_ok = end == len(text) or not _CJK_RE.match(text[end])
        if before_ok and after_ok:
            return start
    return -1


async def generate_vocabulary(
    db: AsyncSession,
    *,
    level: str,
    tags: list[str],
    count: int = 5,
) -> list[ContentItem]:
    """어휘 콘텐츠를 LLM 으로 생성해 DB 에 저장한다.

    부분 성공 허용 — 검증을 통과한 항목만 저장하고 나머지는 스킵.
    LLMError 또는 템플릿 오류는 호출측에서 처리(seed 폴백 등).
    """
    # 1) 프롬프트 렌더링
    try:
        template = _jinja_env.get_template("vocabulary_ja.j2")
    except TemplateNotFound as exc:
        raise RuntimeError("vocabulary_ja.j2 프롬프트 템플릿을 찾을 수 없음") from exc

    prompt = template.render(level=level, tags=tags, count=count)

    # 2) Ollama 호출
    raw = await llm_client.generate_json(prompt)

    # 3) 응답 파싱 — 형식이 맞지 않으면 빈 결과로 처리
    try:
        batch = VocabularyBatch.model_validate(raw)
    except ValidationError as exc:
        logger.warning("LLM 응답 파싱 실패: %s | raw=%s", exc, str(raw)[:200])
        return []

    # 4) 검증 + DB 저장
    saved: list[ContentItem] = []
    now = datetime.now(timezone.utc)

    for vocab in batch.items:
        if not validate_vocabulary_output(vocab):
            logger.debug("검증 실패 — 스킵: word=%s", vocab.word)
            continue

        # vocabulary 종류의 payload 구조
        payload = {
            "word": vocab.word,
            "reading": vocab.reading,
            "meaning_ko": vocab.meaning_ko,
            "example_ja": vocab.example_ja,
            "example_ko": vocab.example_ko,
        }
        item = await content_repo.create(
            db,
            language="ja",
            level=level,
            kind="vocabulary",
            tags=vocab.tags or tags,
            payload=payload,
            source="llm",
            quality_score=0.8,
            generated_at=now,
        )
        # ContentItem 당 기본 문제 2~3개 생성
        # distractors 는 Phase 4 에서 풀 기반으로 채움 (현재 null 허용)
        item_tags = vocab.tags or tags

        # MCQ_MEANING: 단어 보고 한국어 의미 고르기
        await content_repo.create_problem(
            db,
            content_item_id=item.id,
            problem_type=ProblemType.MCQ_MEANING,
            prompt=f"{vocab.word}（{vocab.reading}）의 의미는?",
            answer=vocab.meaning_ko,
            distractors=None,
            tags=item_tags,
            meta={},
        )

        # MCQ_READING: 한자 보고 히라가나 읽기 고르기
        await content_repo.create_problem(
            db,
            content_item_id=item.id,
            problem_type=ProblemType.MCQ_READING,
            prompt=f"다음 단어의 읽기를 고르세요: {vocab.word}",
            answer=vocab.reading,
            distractors=None,
            tags=item_tags,
            meta={},
        )

        # FILL_BLANK: 단독 단어 위치를 찾은 경우만 생성 (복합어 내부 오일치 방지)
        _idx = _find_standalone_word(vocab.word, vocab.example_ja)
        if _idx != -1:
            blank_prompt = (
                vocab.example_ja[:_idx] + "＿＿＿" + vocab.example_ja[_idx + len(vocab.word):]
            )
            await content_repo.create_problem(
                db,
                content_item_id=item.id,
                problem_type=ProblemType.FILL_BLANK,
                prompt=blank_prompt,
                answer=vocab.word,
                distractors=None,
                tags=item_tags,
                meta={"example_ko": vocab.example_ko},
            )

        saved.append(item)

    logger.info(
        "어휘 생성 완료: level=%s, 요청=%d, ContentItem=%d",
        level, count, len(saved),
    )
    await db.commit()
    return saved
