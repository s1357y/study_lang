"""MCQ_MEANING 오답 선택지 일괄 보강 스크립트.

distractors 가 NULL 이거나 3개 이하인 기존 MCQ_MEANING 문제에
confusable_meanings 를 LLM 으로 생성해 저장한다.

실행:
    cd backend
    python -m scripts.enrich_mcq_meaning [--level LEVEL] [--dry-run] [--batch-size N] [--upgrade]

동작:
    1) 기본: Problem WHERE type='mcq_meaning' AND distractors IS NULL 조회
       --upgrade: distractors IS NULL 또는 옵션 수 <= 3 인 문제도 대상에 포함
    2) 연결된 ContentItem 에서 word/reading/meaning_ko 추출
    3) LLM 으로 confusable_meanings 6~9개 생성 (enrich_mcq_meaning.j2 프롬프트)
    4) 방어 필터 후 Problem.distractors 업데이트
    멱등성: --upgrade 없이 실행 시 이미 distractors 가 있는 행은 자동 스킵
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
from sqlalchemy import func, or_, select  # noqa: E402
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


async def _fetch_problems(
    db: AsyncSession, *, level: str | None, upgrade: bool
) -> list[tuple[Problem, ContentItem]]:
    """보강 대상 MCQ_MEANING 문제를 조회한다.

    upgrade=False: distractors IS NULL 인 문제만 (기본)
    upgrade=True: 추가로 옵션 수 3개 이하인 문제도 포함
    """
    if upgrade:
        # 3개 이하 → 6~9개로 확장 대상
        distractor_cond = or_(
            Problem.distractors.is_(None),
            func.jsonb_array_length(Problem.distractors["options"]) <= 3,
        )
    else:
        distractor_cond = Problem.distractors.is_(None)

    stmt = (
        select(Problem, ContentItem)
        .join(ContentItem, Problem.content_item_id == ContentItem.id)
        .where(
            Problem.type == ProblemType.MCQ_MEANING,
            distractor_cond,
            ContentItem.language == "ja",
        )
    )
    if level:
        stmt = stmt.where(ContentItem.level == level)

    rows = (await db.execute(stmt)).all()
    return [(row[0], row[1]) for row in rows]


async def _generate_distractors(word: str, reading: str, meaning_ko: str) -> list[str]:
    """LLM 으로 confusable_meanings 6~9개를 생성한다. 실패 시 빈 리스트 반환."""
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

    # 방어 필터: 정답과 동일한 항목 제거, 최대 9개 저장
    filtered = [m for m in parsed.confusable_meanings if m != meaning_ko][:9]
    return filtered


# ---------------------------------------------------------------------------
# 보강 실행
# ---------------------------------------------------------------------------


async def run(*, level: str | None, dry_run: bool, batch_size: int, upgrade: bool) -> None:
    async with SessionLocal() as db:
        pairs = await _fetch_problems(db, level=level, upgrade=upgrade)
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
  python -m scripts.enrich_mcq_meaning --upgrade --dry-run
  python -m scripts.enrich_mcq_meaning --upgrade --level BEGINNER --batch-size 5
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
    parser.add_argument(
        "--upgrade",
        action="store_true",
        help="distractors 가 3개 이하인 기존 레코드도 보강 대상에 포함",
    )
    return parser.parse_args()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    args = _parse_args()
    asyncio.run(
        run(
            level=args.level, dry_run=args.dry_run, batch_size=args.batch_size, upgrade=args.upgrade
        )
    )
