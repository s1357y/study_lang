"""콘텐츠 시딩 스크립트 — seeds/vocabulary_n5.json 을 DB 에 INSERT 한다.

실행:
    cd backend
    python -m scripts.seed_content [--level BEGINNER] [--dry-run]

동작:
    1) seeds/vocabulary_n5.json 로드
    2) content_repo.get_seeds() 로 기존 seed 확인 (중복 방지)
    3) 없는 항목만 ContentItem INSERT (source="seed")
    4) MCQ_MEANING 필수 / MCQ_READING 한자 있을 때 / FILL_BLANK 단독 출현 때
    5) 전체 완료 후 한 번 commit (부분 삽입 없음)
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

# python scripts/seed_content.py 직접 실행 시 app.* 임포트 보장
_BACKEND = Path(__file__).parent.parent
sys.path.insert(0, str(_BACKEND))

from app.core.db import SessionLocal  # noqa: E402
from app.core.logging import get_logger  # noqa: E402
from app.models.problem import ProblemType  # noqa: E402
from app.repositories import content_repo  # noqa: E402

logger = get_logger("seed_content")

_SEEDS_FILE = _BACKEND / "seeds" / "vocabulary_n5.json"

# generation_service._find_standalone_word 와 동일 패턴 — CJK 한자 경계 판단
_CJK_RE = re.compile(r"[一-鿿]")
# 한자 포함 여부 판단용 (히라가나/가타카나만인 단어는 MCQ_READING 불필요)
_KANJI_RE = re.compile(r"[一-鿿]")


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------


def _has_kanji(text: str) -> bool:
    return bool(_KANJI_RE.search(text))


def _find_standalone_idx(word: str, text: str) -> int:
    """단독 출현 첫 번째 인덱스 반환, 없으면 -1.

    generation_service._find_standalone_word 와 동일 로직.
    직전·직후 문자가 한자이면 복합어 내부로 간주하고 스킵.
    """
    for m in re.finditer(re.escape(word), text):
        start, end = m.start(), m.end()
        before_ok = start == 0 or not _CJK_RE.match(text[start - 1])
        after_ok = end == len(text) or not _CJK_RE.match(text[end])
        if before_ok and after_ok:
            return start
    return -1


# ---------------------------------------------------------------------------
# 메인
# ---------------------------------------------------------------------------


async def run(*, level: str, dry_run: bool) -> None:
    raw = json.loads(_SEEDS_FILE.read_text(encoding="utf-8"))
    items: list[dict] = raw["items"]
    logger.info("seeds 파일 로드: %d개 (level=%s)", len(items), level)

    async with SessionLocal() as db:
        existing = await content_repo.get_seeds(db, language="ja", level=level)
        seen_words: set[str] = {ci.payload["word"] for ci in existing}
        logger.info("기존 seed: %d개", len(seen_words))

        now = datetime.now(UTC)
        n_items = n_problems = n_skip = 0

        for v in items:
            word = v["word"]

            if word in seen_words:
                n_skip += 1
                logger.debug("스킵 (중복): %s", word)
                continue

            # dry-run 시에는 DB 작업 없이 카운트만
            if dry_run:
                n_problems += _count_problems(v)
                n_items += 1
                logger.info("[DRY-RUN] %s (%s) → Problem %d개",
                            word, v["reading"], _count_problems(v))
                continue

            # ContentItem 생성 (flush 만)
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

            # MCQ_MEANING — 항상 생성
            await content_repo.create_problem(
                db,
                content_item_id=item.id,
                problem_type=ProblemType.MCQ_MEANING,
                prompt=f"{word}（{v['reading']}）의 의미는?",
                answer=v["meaning_ko"],
                distractors=None,   # study_service 가 런타임에 같은 레벨 풀에서 채움
                tags=item_tags,
                meta={},
            )
            n_problems += 1

            # MCQ_READING — 단어에 한자가 있을 때만 (읽기가 비자명한 경우)
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

            # FILL_BLANK — 사전형이 예문에 단독으로 출현할 때만
            idx = _find_standalone_idx(word, v["example_ja"])
            if idx != -1:
                blank = (
                    v["example_ja"][:idx]
                    + "＿＿＿"
                    + v["example_ja"][idx + len(word):]
                )
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
            logger.info("commit 완료")

    prefix = "[DRY-RUN] " if dry_run else ""
    logger.info(
        "%s시딩 완료: ContentItem=%d Problem=%d 스킵=%d",
        prefix, n_items, n_problems, n_skip,
    )


def _count_problems(v: dict) -> int:
    """dry-run 용 — 실제 생성될 Problem 수 계산."""
    count = 1  # MCQ_MEANING 항상
    if _has_kanji(v["word"]):
        count += 1
    if _find_standalone_idx(v["word"], v["example_ja"]) != -1:
        count += 1
    return count


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="LingoLab 콘텐츠 시딩 스크립트",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예:
  cd backend
  python -m scripts.seed_content
  python -m scripts.seed_content --level BEGINNER --dry-run
        """,
    )
    parser.add_argument(
        "--level",
        default="BEGINNER",
        choices=["BEGINNER", "ELEMENTARY", "INTERMEDIATE", "ADVANCED"],
        help="시딩할 난이도 레벨 (기본값: BEGINNER)",
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
    asyncio.run(run(level=args.level, dry_run=args.dry_run))
