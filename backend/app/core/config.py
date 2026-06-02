"""환경 설정 (pydantic-settings). 모든 환경변수 접근의 단일 진입점."""

from __future__ import annotations

import json
from functools import lru_cache
from urllib.parse import urlparse, urlunparse

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # 루트의 .env 를 우선 로드하고, 없으면 backend 로컬 .env 사용
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Database (backend only) ---
    database_url: str = Field(
        default="postgresql+asyncpg://studylang:studylang@localhost:5432/studylang",
        alias="DATABASE_URL",
    )

    # --- JWT / 인증 ---
    # access/refresh 모두 동일 시크릿으로 HS256 서명. 운영에선 32바이트 이상.
    jwt_secret: str = Field(default="change-me-to-a-long-random-string", alias="JWT_SECRET")
    jwt_access_ttl_seconds: int = Field(default=900, alias="JWT_ACCESS_TTL_SECONDS")
    jwt_refresh_ttl_seconds: int = Field(default=2592000, alias="JWT_REFRESH_TTL_SECONDS")

    # --- Refresh 쿠키 옵션 ---
    # 빈 문자열이면 host-only (localhost 등 단일 호스트). 운영에선 ".lingolab.io" 같은 공유 도메인.
    refresh_cookie_domain: str = Field(default="", alias="REFRESH_COOKIE_DOMAIN")
    # 운영(HTTPS)에선 True. dev HTTP 환경에선 False 로 둠.
    refresh_cookie_secure: bool = Field(default=False, alias="REFRESH_COOKIE_SECURE")
    # 브라우저가 refresh 쿠키를 보낼 경로 — auth 엔드포인트에만 노출
    refresh_cookie_path: str = Field(default="/api/v1/auth", alias="REFRESH_COOKIE_PATH")

    # --- Ollama ---
    ollama_host: str = Field(default="http://localhost:11434", alias="OLLAMA_HOST")
    ollama_model: str = Field(default="qwen2.5:7b-instruct", alias="OLLAMA_MODEL")

    # --- 자동 마이그레이션 ---
    # 앱 기동 시 Alembic 스키마 드리프트를 감지해 자동 리비전 생성·적용.
    # 운영 환경에서는 False 로 설정해 수동 migrate.ps1 사용 권장.
    auto_migrate: bool = Field(default=True, alias="AUTO_MIGRATE")

    # --- CORS ---
    # 콤마 구분 문자열 또는 JSON 배열 둘 다 허용 (validator 가 정규화)
    cors_allow_origins: list[str] = Field(
        default=["http://localhost:3000"],
        alias="CORS_ALLOW_ORIGINS",
    )

    @field_validator("cors_allow_origins", mode="before")
    @classmethod
    def _split_origins(cls, raw: object) -> object:
        # 이미 리스트면 그대로
        if isinstance(raw, list):
            return raw
        if not isinstance(raw, str):
            return raw
        stripped = raw.strip()
        if not stripped:
            return []
        # JSON 배열 형태 ("[...]") 우선 시도, 실패 시 콤마 분리
        if stripped.startswith("["):
            try:
                return json.loads(stripped)
            except json.JSONDecodeError:
                pass
        return [item.strip() for item in stripped.split(",") if item.strip()]

    @staticmethod
    def _strip_query(url: str) -> str:
        # 쿼리스트링 제거 — split("?") 대신 urlparse 사용 (비밀번호에 ? 가 포함될 수 있음)
        parsed = urlparse(url)
        return urlunparse(parsed._replace(query="", fragment=""))

    @property
    def database_url_async(self) -> str:
        # SQLAlchemy async (asyncpg) 용 URL 정규화
        url = self.database_url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        # Prisma 호환용 ?schema=public 같은 쿼리는 asyncpg가 인식 못 함 → 제거
        return self._strip_query(url)

    @property
    def database_url_sync(self) -> str:
        # Alembic(psycopg2) 동기 URL — 보조 마이그레이션에서만 사용
        url = self.database_url
        if url.startswith("postgresql+asyncpg://"):
            url = url.replace("postgresql+asyncpg://", "postgresql://", 1)
        return self._strip_query(url)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
