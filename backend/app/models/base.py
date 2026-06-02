"""SQLAlchemy DeclarativeBase 단일 출처.

모든 ORM 모델은 이 Base 를 상속한다. Alembic env.py 가 이 Base.metadata 를
target_metadata 로 참조하여 마이그레이션을 자동 생성한다.

Phase 1.5 시점에는 모델 자체는 없음 (Phase 2 에서 User, RefreshToken 부터 추가).
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
