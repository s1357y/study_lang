"""Alembic 환경 — 스키마 단일 출처는 app.models.Base.metadata.

흐름:
- online/offline 모드 모두 동기 psycopg2 URL 사용
- asyncio.to_thread 에서 호출되므로 asyncio.run() 중첩을 피하기 위해 동기 엔진 사용
- target_metadata 를 Base.metadata 로 연결하여 --autogenerate 가 동작
- 새 모델 파일은 app.models 패키지에 import 되어야 자동 감지됨
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from app.core.config import settings
from app.models import Base  # noqa: F401  — Base.metadata 등록을 위해 import

config = context.config
# psycopg2 동기 URL 사용 — asyncio.to_thread 컨텍스트에서 asyncio.run() 중첩 방지
config.set_main_option("sqlalchemy.url", settings.database_url_sync)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# autogenerate 가 참조할 메타데이터 (모든 모델의 단일 출처)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url_sync,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # 동기 엔진으로 연결 — asyncio.to_thread 내에서 asyncio.run() 중첩 없이 안전하게 실행
    connectable = create_engine(settings.database_url_sync, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
