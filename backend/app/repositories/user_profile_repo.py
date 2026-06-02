"""UserProfile CRUD — 사용자 약점 태그 통계 저장소.

흐름:
- get_or_create: 없으면 빈 프로필 생성, 경쟁 조건은 IntegrityError 포착 후 재조회
- update_tag_stats: JSONB 인-플레이스 변경 후 flag_modified 로 dirty 플래그 강제 설정
  (SQLAlchemy 는 JSONB dict 내부 변경을 자동 감지하지 못하므로 반드시 호출해야 함)
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models.user_profile import UserProfile


async def get_global_weak_tags(db: AsyncSession, *, top_n: int = 5) -> list[str]:
    """전체 사용자 tag_stats 를 집계해 공통 약점 태그 상위 N개 반환.

    seen >= 3 이고 오답률(wrong/seen) 평균이 높은 태그를 우선한다.
    pregen 워커처럼 사용자가 특정되지 않는 맥락에서 사용.
    """
    result = await db.execute(select(UserProfile.tag_stats))
    all_stats = result.scalars().all()

    # 태그별 (seen 합계, wrong 합계) 집계
    totals: dict[str, dict[str, int]] = {}
    for stats in all_stats:
        if not stats:
            continue
        for tag, entry in stats.items():
            agg = totals.setdefault(tag, {"seen": 0, "wrong": 0})
            agg["seen"] += entry.get("seen", 0)
            agg["wrong"] += entry.get("wrong", 0)

    # seen >= 3 인 태그만 대상, 오답률 내림차순 상위 N개
    candidates = [
        (tag, agg["wrong"] / agg["seen"])
        for tag, agg in totals.items()
        if agg["seen"] >= 3
    ]
    candidates.sort(key=lambda x: x[1], reverse=True)
    return [tag for tag, _ in candidates[:top_n]]


async def get_or_create(db: AsyncSession, *, user_id: UUID) -> UserProfile:
    stmt = select(UserProfile).where(UserProfile.user_id == user_id)
    result = await db.execute(stmt)
    profile = result.scalar_one_or_none()
    if profile is not None:
        return profile

    # 없으면 빈 프로필 생성, 동시 삽입 경쟁 방어
    try:
        profile = UserProfile(user_id=user_id)
        db.add(profile)
        await db.flush()
        return profile
    except IntegrityError:
        await db.rollback()
        result = await db.execute(stmt)
        return result.scalar_one()


def update_tag_stats(
    profile: UserProfile,
    *,
    tags: list[str],
    correct: bool,
) -> None:
    # JSONB 내부 변경은 SQLAlchemy 가 감지 못하므로 직접 수정 후 flag_modified 필수
    stats: dict = dict(profile.tag_stats)  # 얕은 복사로 새 dict 참조 생성
    now_iso = datetime.now(timezone.utc).isoformat()

    for tag in tags:
        entry = stats.get(tag, {"seen": 0, "wrong": 0, "last_wrong_at": None})
        entry["seen"] += 1
        if not correct:
            entry["wrong"] += 1
            entry["last_wrong_at"] = now_iso
        stats[tag] = entry

    profile.tag_stats = stats
    flag_modified(profile, "tag_stats")
