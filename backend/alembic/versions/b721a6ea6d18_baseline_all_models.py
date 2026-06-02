"""baseline_all_models + problem type 소문자 통일

Revision ID: b721a6ea6d18
Revises: 23e1e562d141
Create Date: 2026-06-02 16:29:26.070662

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b721a6ea6d18'
down_revision: Union[str, None] = '23e1e562d141'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# ProblemType 값을 대문자 → 소문자로 변환 (프론트 Zod 스키마 동기화)
_TYPE_MAP = {
    "MCQ_MEANING": "mcq_meaning",
    "MCQ_READING": "mcq_reading",
    "FILL_BLANK":  "fill_blank",
    "TRANSLATION": "translation",
    "LISTENING":   "listening",
}


def upgrade() -> None:
    conn = op.get_bind()
    for old, new in _TYPE_MAP.items():
        conn.execute(
            sa.text("UPDATE problem SET type = :new WHERE type = :old"),
            {"new": new, "old": old},
        )


def downgrade() -> None:
    # 소문자 → 대문자로 롤백
    conn = op.get_bind()
    for old, new in _TYPE_MAP.items():
        conn.execute(
            sa.text("UPDATE problem SET type = :old WHERE type = :new"),
            {"old": old, "new": new},
        )
