"""LLM 호출 오케스트레이션 — 프롬프트 렌더링 → Ollama 호출 → 검증 → DB 저장.

흐름:
1. Jinja2 템플릿으로 프롬프트 생성 (level + weak_tags 주입)
2. llm_client.generate_json() 으로 Ollama 호출
3. VocabularyBatch/GrammarBatch 파싱 + 검증
4. 검증 통과 항목만 content_repo.create() 로 DB 저장
5. 생성된 ContentItem 목록 반환

이 모듈은 LLM 을 사용하는 유일한 서비스. 직접 httpx 호출 금지.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, TemplateNotFound
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.llm import client as llm_client
from app.llm.schemas import GrammarBatch, VocabularyBatch
from app.llm.validators import validate_vocabulary_output
from app.models.content_item import ContentItem
from app.models.problem import ProblemType
from app.repositories import content_repo

logger = get_logger(__name__)

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
    """
    try:
        template = _jinja_env.get_template("vocabulary_ja.j2")
    except TemplateNotFound as exc:
        raise RuntimeError("vocabulary_ja.j2 프롬프트 템플릿을 찾을 수 없음") from exc

    prompt = template.render(level=level, tags=tags, count=count)
    raw = await llm_client.generate_json(prompt)

    try:
        batch = VocabularyBatch.model_validate(raw)
    except ValidationError as exc:
        logger.warning("LLM 응답 파싱 실패: %s | raw=%s", exc, str(raw)[:200])
        return []

    saved: list[ContentItem] = []
    now = datetime.now(UTC)

    for vocab in batch.items:
        if not validate_vocabulary_output(vocab):
            logger.debug("검증 실패 — 스킵: word=%s", vocab.word)
            continue

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
        item_tags = vocab.tags or tags

        # MCQ_MEANING: 단어 보고 한국어 의미 고르기
        # 정답과 동일한 항목을 방어 필터로 제거 (LLM이 정답을 오답 칸에 넣는 케이스 방지)
        safe_cm = [m for m in vocab.confusable_meanings if m != vocab.meaning_ko][:9]
        await content_repo.create_problem(
            db,
            content_item_id=item.id,
            problem_type=ProblemType.MCQ_MEANING,
            prompt=f"{vocab.word}（{vocab.reading}）의 의미는?",
            answer=vocab.meaning_ko,
            distractors={"options": safe_cm} if safe_cm else None,
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

        # FILL_BLANK: 단독 단어 위치를 찾은 경우만 생성
        _idx = _find_standalone_word(vocab.word, vocab.example_ja)
        if _idx != -1:
            blank_prompt = (
                vocab.example_ja[:_idx] + "＿＿＿" + vocab.example_ja[_idx + len(vocab.word) :]
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

        # MCQ_CONTEXT: 예문 문맥에서 단어 의미 선택 — 동일 레벨 의미 3개를 distractors 로 선저장
        ctx_distractors = await _collect_meaning_distractors(
            db, level=level, exclude_id=item.id, correct=vocab.meaning_ko
        )
        if len(ctx_distractors) >= 3 and _idx != -1:
            # 단어가 예문에 단독으로 나타나는 경우에만 생성
            ctx_blank = (
                vocab.example_ja[:_idx]
                + f"「{vocab.word}」"
                + vocab.example_ja[_idx + len(vocab.word) :]
            )
            await content_repo.create_problem(
                db,
                content_item_id=item.id,
                problem_type=ProblemType.MCQ_CONTEXT,
                prompt=f"다음 문장의 「{vocab.word}」의 의미는?\n{ctx_blank}",
                answer=vocab.meaning_ko,
                distractors={"options": ctx_distractors[:3]},
                tags=item_tags,
                meta={},
            )

        # MCQ_SYNONYM: 유의어 정답 + 다른 단어의 의미 3개를 오답으로 선저장
        # synonyms 자체를 오답으로 쓰면 복수 정답 문제가 생기므로, pool 에서 오답 조달
        if vocab.synonyms:
            syn_answer = vocab.synonyms[0]
            syn_distractors = await _collect_meaning_distractors(
                db, level=level, exclude_id=item.id, correct=syn_answer
            )
            if len(syn_distractors) >= 3:
                await content_repo.create_problem(
                    db,
                    content_item_id=item.id,
                    problem_type=ProblemType.MCQ_SYNONYM,
                    prompt=(
                        f"「{vocab.word}（{vocab.reading}）」과 의미가 가장 가까운 표현을 고르세요."
                    ),
                    answer=syn_answer,
                    distractors={"options": syn_distractors[:3]},
                    tags=item_tags,
                    meta={},
                )

        saved.append(item)

    logger.info("어휘 생성 완료: level=%s, 요청=%d, ContentItem=%d", level, count, len(saved))
    await db.commit()
    return saved


async def generate_grammar_content(
    db: AsyncSession,
    *,
    level: str,
    tags: list[str],
    count: int = 5,
) -> list[ContentItem]:
    """문법 콘텐츠를 LLM 으로 생성해 DB 에 저장한다."""
    # seed + llm 생성 항목 모두 포함해 중복 방지 (get_seeds는 source="seed"만 반환)
    existing = await content_repo.get_pool(
        db, language="ja", level=level, kind="grammar", limit=200
    )
    existing_patterns = [ci.payload.get("grammar_point", "") for ci in existing]

    try:
        template = _jinja_env.get_template("grammar_ja.j2")
    except TemplateNotFound as exc:
        raise RuntimeError("grammar_ja.j2 프롬프트 템플릿을 찾을 수 없음") from exc

    prompt = template.render(
        level=level, tags=tags, count=count, existing_patterns=existing_patterns
    )
    raw = await llm_client.generate_json(prompt)

    try:
        batch = GrammarBatch.model_validate(raw)
    except ValidationError as exc:
        logger.warning("문법 LLM 응답 파싱 실패: %s | raw=%s", exc, str(raw)[:200])
        return []

    saved: list[ContentItem] = []
    now = datetime.now(UTC)

    for grammar in batch.items:
        if not grammar.grammar_point or not grammar.example_ja:
            logger.debug("필수 필드 누락 — 스킵: %s", grammar.grammar_point)
            continue

        payload = {
            "grammar_point": grammar.grammar_point,
            "pattern_ja": grammar.pattern_ja,
            "meaning_ko": grammar.meaning_ko,
            "usage_ko": grammar.usage_ko,
            "example_ja": grammar.example_ja,
            "example_ko": grammar.example_ko,
            "similar_patterns": grammar.similar_patterns,
            "wrong_patterns": grammar.wrong_patterns,
        }
        item = await content_repo.create(
            db,
            language="ja",
            level=level,
            kind="grammar",
            tags=grammar.tags or tags,
            payload=payload,
            source="llm",
            quality_score=0.8,
            generated_at=now,
        )
        item_tags = grammar.tags or tags

        # MCQ_GRAMMAR: 예문 빈칸 — grammar_point 에서 〜 제거해 answer 추출
        answer = grammar.grammar_point.lstrip("〜")
        idx = grammar.example_ja.find(answer)
        if idx != -1:
            blank_prompt = (
                grammar.example_ja[:idx] + "___" + grammar.example_ja[idx + len(answer) :]
            )
        else:
            blank_prompt = grammar.example_ja

        if len(grammar.wrong_patterns) >= 3:
            await content_repo.create_problem(
                db,
                content_item_id=item.id,
                problem_type=ProblemType.MCQ_GRAMMAR,
                prompt=blank_prompt,
                answer=answer,
                distractors={"options": grammar.wrong_patterns[:3]},
                tags=item_tags,
                meta={"grammar_point": grammar.grammar_point},
            )
        else:
            logger.warning("MCQ_GRAMMAR distractors 부족 — 스킵: %s", grammar.grammar_point)

        saved.append(item)

    logger.info("문법 생성 완료: level=%s, 요청=%d, ContentItem=%d", level, count, len(saved))
    await db.commit()
    return saved


async def _collect_meaning_distractors(
    db: AsyncSession,
    *,
    level: str,
    exclude_id,
    correct: str,
) -> list[str]:
    """동일 레벨 vocabulary 에서 의미(meaning_ko) 최대 3개를 distractor 후보로 수집."""
    pool = await content_repo.get_items_by_level_excluding(
        db, level=level, exclude_id=exclude_id, kind="vocabulary", limit=20
    )
    candidates: list[str] = []
    seen: set[str] = {correct}
    for ci in pool:
        val = ci.payload.get("meaning_ko", "")
        if val and val not in seen:
            seen.add(val)
            candidates.append(val)
        if len(candidates) >= 3:
            break
    return candidates
