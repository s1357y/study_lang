"""배치 시험 Pydantic 스키마."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

_LEVEL_LABELS: dict[str, str] = {
    "BEGINNER": "초급 (N5)",
    "ELEMENTARY": "초중급 (N4)",
    "INTERMEDIATE": "중급 (N3)",
    "ADVANCED": "고급 (N2/N1)",
}


class PlacementProblemOut(BaseModel):
    # level 필드 없음 — 클라이언트에 레벨 노출 방지
    problem_id: UUID
    content_item_id: UUID
    problem_type: str
    prompt: str
    answer: str
    distractors: list[str]
    tags: list[str]


class PlacementProblemsOut(BaseModel):
    problems: list[PlacementProblemOut]
    total: int
    # HMAC-서명 토큰 — submit 시 반드시 포함해야 함
    placement_token: str


class PlacementSubmitIn(BaseModel):
    # GET /placement/problems 응답에서 받은 서명 토큰
    placement_token: str
    # problem_id(str) → 정답 여부
    answers: dict[str, bool]


class PlacementResultOut(BaseModel):
    assigned_level: str
    level_label: str
    message: str

    @classmethod
    def from_level(cls, level: str) -> PlacementResultOut:
        label = _LEVEL_LABELS.get(level, level)
        return cls(
            assigned_level=level,
            level_label=label,
            message=f"배치 시험 완료! 당신의 레벨은 {label}입니다.",
        )
