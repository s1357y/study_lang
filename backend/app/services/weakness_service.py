"""약점 서비스 — 사용자별 태그 통계 관리.

흐름:
- record_attempt: 시도 결과를 user_profile 에 누적 (tag_stats 갱신)
- get_weak_tags: seen >= 3 이고 오답률 높은 태그 상위 N개 반환
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import user_profile_repo


async def record_attempt(
    db: AsyncSession,
    *,
    user_id: UUID,
    tags: list[str],
    correct: bool,
) -> None:
    # 프로필 없으면 자동 생성 후 태그 통계 업데이트
    profile = await user_profile_repo.get_or_create(db, user_id=user_id)
    user_profile_repo.update_tag_stats(profile, tags=tags, correct=correct)


async def get_weak_tags(
    db: AsyncSession,
    *,
    user_id: UUID,
    top_n: int = 5,
) -> list[str]:
    profile = await user_profile_repo.get_or_create(db, user_id=user_id)
    stats: dict = profile.tag_stats

    # seen >= 3 인 태그만 대상, 오답률(wrong/seen) 내림차순 상위 N개
    candidates = [
        (tag, entry["wrong"] / entry["seen"])
        for tag, entry in stats.items()
        if entry.get("seen", 0) >= 3
    ]
    candidates.sort(key=lambda x: x[1], reverse=True)
    return [tag for tag, _ in candidates[:top_n]]
