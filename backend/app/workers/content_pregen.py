"""콘텐츠 사전 생성 워커 — APScheduler 로 주기적으로 풀을 보충한다.

동작:
- 10분 간격으로 레벨별 풀 크기를 확인
- 임계치(POOL_MIN) 미만이면 generation_service 로 배치 생성
- LLM 오류는 로그만 남기고 다음 주기에 재시도

main.py 의 lifespan 이벤트에서 start/stop 을 호출한다.
"""

from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.db import SessionLocal
from app.core.logging import get_logger
from app.llm.client import LLMError
from app.repositories import user_profile_repo
from app.services import generation_service
from app.services.content_service import get_pool_stats

logger = get_logger(__name__)

# 레벨별 최소 풀 크기 — 이 값 미만이면 배치 생성 트리거
POOL_MIN = 50

# 배치당 생성 수
BATCH_SIZE = 10

# 관리 대상 레벨
MANAGED_LEVELS = ["BEGINNER", "ELEMENTARY", "INTERMEDIATE", "ADVANCED"]

_scheduler = AsyncIOScheduler()


async def _pregen_task() -> None:
    # 레벨별 풀 확인 + 전체 사용자 공통 약점 태그 조회
    async with SessionLocal() as db:
        stats = await get_pool_stats(db)
        weak_tags = await user_profile_repo.get_global_weak_tags(db, top_n=5)

    if weak_tags:
        logger.info("사전 생성 약점 태그 주입: %s", weak_tags)

    for level in MANAGED_LEVELS:
        current = stats.get(level, 0)
        if current < POOL_MIN:
            needed = POOL_MIN - current
            batches = (needed + BATCH_SIZE - 1) // BATCH_SIZE  # 올림 나눗셈
            logger.info("사전 생성 시작: level=%s, 현재=%d, 필요=%d, 배치=%d", level, current, needed, batches)
            for _ in range(batches):
                try:
                    async with SessionLocal() as db:
                        await generation_service.generate_vocabulary(
                            db, level=level, tags=weak_tags, count=BATCH_SIZE
                        )
                except (LLMError, RuntimeError) as exc:
                    logger.warning("사전 생성 실패 (level=%s): %s", level, exc)
                    break  # 이 레벨은 다음 주기에 재시도


def start_scheduler() -> None:
    # 10분 간격으로 태스크 등록 후 시작
    _scheduler.add_job(_pregen_task, "interval", minutes=10, id="content_pregen")
    _scheduler.start()
    logger.info("콘텐츠 사전 생성 스케줄러 시작 (10분 간격)")


def stop_scheduler() -> None:
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("콘텐츠 사전 생성 스케줄러 종료")
