"""콘텐츠 시딩 스크립트 — seeds/*.json 을 DB 에 INSERT 한다.

실행:
    cd backend
    python -m scripts.seed_content [--level LEVEL] [--kind vocabulary|grammar] [--dry-run]

동작 (vocabulary):
    1) seeds/vocabulary_*.json 로드
    2) content_repo.get_seeds() 로 기존 seed 확인 (중복 방지)
    3) MCQ_MEANING 필수 / MCQ_READING 한자 있을 때 / FILL_BLANK 단독 출현 때

동작 (grammar):
    1) seeds/grammar_*.json 로드
    2) grammar_point 중복 방지
    3) MCQ_GRAMMAR — blank_word 를 예문에서 찾아 빈칸 생성, wrong_patterns 를 distractors 로 선저장
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

_BACKEND = Path(__file__).parent.parent
sys.path.insert(0, str(_BACKEND))

from app.core.db import SessionLocal  # noqa: E402
from app.core.logging import get_logger  # noqa: E402
from app.models.problem import ProblemType  # noqa: E402
from app.repositories import content_repo  # noqa: E402

logger = get_logger("seed_content")

_VOCAB_LEVEL_TO_FILE = {
    "BEGINNER": _BACKEND / "seeds" / "vocabulary_n5.json",
    "ELEMENTARY": _BACKEND / "seeds" / "vocabulary_n4.json",
    "INTERMEDIATE": _BACKEND / "seeds" / "vocabulary_n3.json",
    "ADVANCED": _BACKEND / "seeds" / "vocabulary_n2.json",
}

_GRAMMAR_LEVEL_TO_FILE = {
    "ELEMENTARY": _BACKEND / "seeds" / "grammar_n4.json",
    "INTERMEDIATE": _BACKEND / "seeds" / "grammar_n3.json",
}

# CJK 한자 경계 판단용
_CJK_RE = re.compile(r"[一-鿿]")
_KANJI_RE = re.compile(r"[一-鿿]")


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------


def _has_kanji(text: str) -> bool:
    return bool(_KANJI_RE.search(text))


def _find_standalone_idx(word: str, text: str) -> int:
    """단독 출현 첫 번째 인덱스 반환, 없으면 -1."""
    for m in re.finditer(re.escape(word), text):
        start, end = m.start(), m.end()
        before_ok = start == 0 or not _CJK_RE.match(text[start - 1])
        after_ok = end == len(text) or not _CJK_RE.match(text[end])
        if before_ok and after_ok:
            return start
    return -1


def _make_blank_prompt(text: str, blank_word: str) -> str | None:
    """text 안의 blank_word 첫 번째 출현을 ___ 로 교체. 없으면 None 반환."""
    idx = text.find(blank_word)
    if idx == -1:
        return None
    return text[:idx] + "___" + text[idx + len(blank_word) :]


# ---------------------------------------------------------------------------
# vocabulary 시딩
# ---------------------------------------------------------------------------


async def seed_vocabulary(db, *, level: str, dry_run: bool) -> None:
    seeds_file = _VOCAB_LEVEL_TO_FILE[level]
    raw = json.loads(seeds_file.read_text(encoding="utf-8"))
    items: list[dict] = raw["items"]
    logger.info("vocabulary seeds 로드: %d개 (level=%s)", len(items), level)

    existing = await content_repo.get_seeds(db, language="ja", level=level, kind="vocabulary")
    seen_words: set[str] = {ci.payload["word"] for ci in existing}
    logger.info("기존 vocabulary seed: %d개", len(seen_words))

    now = datetime.now(UTC)
    n_items = n_problems = n_skip = 0

    for v in items:
        word = v["word"]
        if word in seen_words:
            n_skip += 1
            logger.debug("스킵 (중복): %s", word)
            continue

        if dry_run:
            cnt = _count_vocab_problems(v)
            n_problems += cnt
            n_items += 1
            logger.info("[DRY-RUN] %s (%s) → Problem %d개", word, v["reading"], cnt)
            continue

        item = await content_repo.create(
            db,
            language="ja",
            level=level,
            kind="vocabulary",
            tags=v.get("tags", ["N5"]),
            payload={
                "word": v["word"],
                "reading": v["reading"],
                "meaning_ko": v["meaning_ko"],
                "example_ja": v["example_ja"],
                "example_ko": v.get("example_ko", ""),
            },
            source="seed",
            quality_score=0.8,
            generated_at=now,
        )
        item_tags = v.get("tags", ["N5"])

        # MCQ_MEANING — 항상 생성 (confusable_meanings 있으면 선저장, 없으면 None)
        # 정답과 동일한 항목은 방어 필터로 제거
        cm = [m for m in v.get("confusable_meanings", []) if m != v["meaning_ko"]][:3]
        await content_repo.create_problem(
            db,
            content_item_id=item.id,
            problem_type=ProblemType.MCQ_MEANING,
            prompt=f"{word}（{v['reading']}）의 의미는?",
            answer=v["meaning_ko"],
            distractors={"options": cm} if cm else None,
            tags=item_tags,
            meta={},
        )
        n_problems += 1

        # MCQ_READING — 한자 포함 단어에만
        if _has_kanji(word):
            await content_repo.create_problem(
                db,
                content_item_id=item.id,
                problem_type=ProblemType.MCQ_READING,
                prompt=f"다음 단어의 읽기를 고르세요: {word}",
                answer=v["reading"],
                distractors=None,
                tags=item_tags,
                meta={},
            )
            n_problems += 1

        # FILL_BLANK — 예문에 단어가 단독으로 출현할 때만
        idx = _find_standalone_idx(word, v["example_ja"])
        if idx != -1:
            blank = v["example_ja"][:idx] + "＿＿＿" + v["example_ja"][idx + len(word) :]
            await content_repo.create_problem(
                db,
                content_item_id=item.id,
                problem_type=ProblemType.FILL_BLANK,
                prompt=blank,
                answer=word,
                distractors=None,
                tags=item_tags,
                meta={"example_ko": v.get("example_ko", "")},
            )
            n_problems += 1

        n_items += 1

    if not dry_run and n_items > 0:
        await db.commit()
        logger.info("vocabulary commit 완료")

    prefix = "[DRY-RUN] " if dry_run else ""
    logger.info(
        "%svocabulary 시딩 완료: ContentItem=%d Problem=%d 스킵=%d",
        prefix,
        n_items,
        n_problems,
        n_skip,
    )


def _count_vocab_problems(v: dict) -> int:
    count = 1
    if _has_kanji(v["word"]):
        count += 1
    if _find_standalone_idx(v["word"], v["example_ja"]) != -1:
        count += 1
    return count


# ---------------------------------------------------------------------------
# grammar 시딩
# ---------------------------------------------------------------------------


async def seed_grammar(db, *, level: str, dry_run: bool) -> None:
    seeds_file = _GRAMMAR_LEVEL_TO_FILE.get(level)
    if seeds_file is None or not seeds_file.exists():
        logger.warning("grammar 시드 파일 없음 (level=%s)", level)
        return

    raw = json.loads(seeds_file.read_text(encoding="utf-8"))
    items: list[dict] = raw["items"]
    logger.info("grammar seeds 로드: %d개 (level=%s)", len(items), level)

    existing = await content_repo.get_seeds(db, language="ja", level=level, kind="grammar")
    seen_points: set[str] = {ci.payload["grammar_point"] for ci in existing}
    logger.info("기존 grammar seed: %d개", len(seen_points))

    now = datetime.now(UTC)
    n_items = n_problems = n_skip = 0

    for g in items:
        gp = g["grammar_point"]
        if gp in seen_points:
            n_skip += 1
            logger.debug("스킵 (중복): %s", gp)
            continue

        if dry_run:
            n_items += 1
            n_problems += 1
            logger.info("[DRY-RUN] %s → MCQ_GRAMMAR 1개", gp)
            continue

        item_tags = g.get("tags", ["grammar"])
        item = await content_repo.create(
            db,
            language="ja",
            level=level,
            kind="grammar",
            tags=item_tags,
            payload={
                "grammar_point": g["grammar_point"],
                "pattern_ja": g.get("pattern_ja", g["grammar_point"]),
                "meaning_ko": g["meaning_ko"],
                "usage_ko": g.get("usage_ko", ""),
                "example_ja": g["example_ja"],
                "example_ko": g.get("example_ko", ""),
                "similar_patterns": g.get("similar_patterns", []),
                "wrong_patterns": g.get("wrong_patterns", []),
            },
            source="seed",
            quality_score=0.8,
            generated_at=now,
        )

        # MCQ_GRAMMAR — blank_word 로 빈칸 생성, wrong_patterns 를 선저장
        blank_word: str = g.get("blank_word") or gp.lstrip("〜")
        blank_prompt = _make_blank_prompt(g["example_ja"], blank_word)
        # example_ja가 이미 ___ 로 작성된 시드 항목은 그대로 사용
        if blank_prompt is None and "___" in g["example_ja"]:
            blank_prompt = g["example_ja"]

        wrong = g.get("wrong_patterns", [])[:3]
        if blank_prompt and wrong:
            await content_repo.create_problem(
                db,
                content_item_id=item.id,
                problem_type=ProblemType.MCQ_GRAMMAR,
                prompt=blank_prompt,
                answer=blank_word,
                distractors={"options": wrong},
                tags=item_tags,
                meta={"grammar_point": gp},
            )
            n_problems += 1
        else:
            logger.warning("MCQ_GRAMMAR 생성 스킵 — blank 없음 또는 distractors 부족: %s", gp)

        n_items += 1

    if not dry_run and n_items > 0:
        await db.commit()
        logger.info("grammar commit 완료")

    prefix = "[DRY-RUN] " if dry_run else ""
    logger.info(
        "%sgrammar 시딩 완료: ContentItem=%d Problem=%d 스킵=%d",
        prefix,
        n_items,
        n_problems,
        n_skip,
    )


# ---------------------------------------------------------------------------
# 진입점
# ---------------------------------------------------------------------------


async def run(*, level: str, kind: str, dry_run: bool) -> None:
    async with SessionLocal() as db:
        if kind == "vocabulary":
            await seed_vocabulary(db, level=level, dry_run=dry_run)
        else:
            await seed_grammar(db, level=level, dry_run=dry_run)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="LingoLab 콘텐츠 시딩 스크립트",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예:
  cd backend
  python -m scripts.seed_content
  python -m scripts.seed_content --level BEGINNER --dry-run
  python -m scripts.seed_content --level ELEMENTARY --kind grammar
  python -m scripts.seed_content --level INTERMEDIATE --kind grammar --dry-run
        """,
    )
    parser.add_argument(
        "--level",
        default="BEGINNER",
        choices=["BEGINNER", "ELEMENTARY", "INTERMEDIATE", "ADVANCED"],
        help="시딩할 난이도 레벨 (기본값: BEGINNER)",
    )
    parser.add_argument(
        "--kind",
        default="vocabulary",
        choices=["vocabulary", "grammar"],
        help="시딩할 콘텐츠 종류 (기본값: vocabulary)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="DB 변경 없이 시딩 계획만 출력",
    )
    return parser.parse_args()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    args = _parse_args()
    asyncio.run(run(level=args.level, kind=args.kind, dry_run=args.dry_run))
