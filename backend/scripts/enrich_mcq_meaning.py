"""MCQ_MEANING 오답 선택지 일괄 보강 스크립트.

distractors 가 NULL 인 기존 MCQ_MEANING 문제에 confusable_meanings 를 LLM 으로 생성해 저장한다.

실행:
    cd backend
    python -m scripts.enrich_mcq_meaning [--level LEVEL] [--dry-run] [--batch-size N]

동작:
    1) Problem WHERE type='mcq_meaning' AND distractors IS NULL 조회 (레벨 필터 선택)
    2) 연결된 ContentItem 에서 word/reading/meaning_ko 추출
    3) LLM 으로 confusable_meanings 3개 생성 (enrich_mcq_meaning.j2 프롬프트)
    4) 방어 필터 후 Problem.distractors 업데이트
    멱등성: 이미 distractors 가 있는 행은 자동 스킵
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

_BACKEND = Path(__file__).parent.parent
sys.path.insert(0, str(_BACKEND))

from jinja2 import Environment, FileSystemLoader, TemplateNotFound  # noqa: E402
from pydantic import BaseModel, Field, ValidationError  # noqa: E402
from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.core.db import SessionLocal  # noqa: E402
from app.core.logging import get_logger  # noqa: E402
from app.llm import client as llm_client  # noqa: E402
from app.models.content_item import ContentItem  # noqa: E402
from app.models.problem import Problem, ProblemType  # noqa: E402

logger = get_logger("enrich_mcq_meaning")

_PROMPTS_DIR = _BACKEND / "app" / "llm" / "prompts"
_jinja_env = Environment(loader=FileSystemLoader(str(_PROMPTS_DIR)), autoescape=False)

_LEVELS = ["BEGINNER", "ELEMENTARY", "INTERMEDIATE", "ADVANCED"]


# ---------------------------------------------------------------------------
# LLM 응답 스키마
# ---------------------------------------------------------------------------


class EnrichOutput(BaseModel):
    confusable_meanings: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------


async def _fetch_null_problems(
    db: AsyncSession, *, level: str | None
) -> list[tuple[Problem, ContentItem]]:
    """distractors 가 NULL 인 MCQ_MEANING 문제와 연결된 ContentItem 을 조회한다."""
    stmt = (
        select(Problem, ContentItem)
        .join(ContentItem, Problem.content_item_id == ContentItem.id)
        .where(
            Problem.type == ProblemType.MCQ_MEANING,
            Problem.distractors.is_(None),
            ContentItem.language == "ja",
        )
    )
    if level:
        stmt = stmt.where(ContentItem.level == level)

    rows = (await db.execute(stmt)).all()
    return [(row[0], row[1]) for row in rows]


async def _generate_distractors(word: str, reading: str, meaning_ko: str) -> list[str]:
    """LLM 으로 confusable_meanings 3개를 생성한다. 실패 시 빈 리스트 반환."""
    try:
        template = _jinja_env.get_template("enrich_mcq_meaning.j2")
    except TemplateNotFound:
        logger.error("enrich_mcq_meaning.j2 템플릿 없음")
        return []

    prompt = template.render(word=word, reading=reading, meaning_ko=meaning_ko)
    try:
        raw = await llm_client.generate_json(prompt)
        parsed = EnrichOutput.model_validate(raw)
    except (ValidationError, Exception) as exc:
        logger.warning("LLM 응답 파싱 실패: %s | word=%s", exc, word)
        return []

    # 방어 필터: 정답과 동일한 항목 제거
    filtered = [m for m in parsed.confusable_meanings if m != meaning_ko][:3]
    return filtered


# ---------------------------------------------------------------------------
# 보강 실행
# ---------------------------------------------------------------------------


async def run(*, level: str | None, dry_run: bool, batch_size: int) -> None:
    async with SessionLocal() as db:
        pairs = await _fetch_null_problems(db, level=level)
        logger.info(
            "보강 대상: %d개 (level=%s, dry_run=%s)",
            len(pairs),
            level or "ALL",
            dry_run,
        )

        n_ok = n_skip = n_fail = 0

        for i, (problem, item) in enumerate(pairs):
            word = item.payload.get("word", "")
            reading = item.payload.get("reading", "")
            meaning_ko = item.payload.get("meaning_ko", "")

            if not word or not meaning_ko:
                logger.warning("payload 누락 — 스킵: problem_id=%s", problem.id)
                n_skip += 1
                continue

            logger.info("[%d/%d] %s(%s)=%s", i + 1, len(pairs), word, reading, meaning_ko)

            if dry_run:
                logger.info("  [DRY-RUN] LLM 호출 스킵")
                n_ok += 1
                continue

            distractors = await _generate_distractors(word, reading, meaning_ko)
            if not distractors:
                logger.warning("  distractors 생성 실패 — 스킵")
                n_fail += 1
                continue

            problem.distractors = {"options": distractors}
            logger.info("  저장: %s", distractors)
            n_ok += 1

            # batch_size 마다 커밋
            if (i + 1) % batch_size == 0 and not dry_run:
                await db.commit()
                logger.info("  [commit] %d개 처리 완료", i + 1)

        if not dry_run:
            await db.commit()

        prefix = "[DRY-RUN] " if dry_run else ""
        logger.info(
            "%s보강 완료: 성공=%d, 실패=%d, 스킵=%d",
            prefix,
            n_ok,
            n_fail,
            n_skip,
        )


# ---------------------------------------------------------------------------
# 진입점
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="MCQ_MEANING 오답 선택지 일괄 보강 스크립트",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예:
  cd backend
  python -m scripts.enrich_mcq_meaning --dry-run
  python -m scripts.enrich_mcq_meaning --level BEGINNER
  python -m scripts.enrich_mcq_meaning --batch-size 5
        """,
    )
    parser.add_argument(
        "--level",
        default=None,
        choices=_LEVELS,
        help="특정 레벨만 보강 (기본값: 전체)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="DB 변경 없이 대상 목록만 출력",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10,
        metavar="N",
        help="커밋 단위 (기본값: 10)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    args = _parse_args()
    asyncio.run(run(level=args.level, dry_run=args.dry_run, batch_size=args.batch_size))
