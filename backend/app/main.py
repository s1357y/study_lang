"""FastAPI app 진입점.

흐름:
- lifespan: APScheduler 시작(콘텐츠 사전 생성) → 앱 실행 → 종료 시 스케줄러 정지
- 로깅 초기화
- CORS 설정 (allow_credentials=True 필수 — refresh 쿠키)
- v1 라우터들을 /api/v1 아래에 등록
- 호환용 루트 /healthz 도 함께 노출 (k8s/lb probe 가정)
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.routes import auth, content, health, motivation, study
from app.core.config import settings
from app.core.logging import configure_logging
from app.core.migration import run_migrations
from app.workers.content_pregen import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # 앱 시작 — 스키마 자동 동기화 후 스케줄러 기동
    if settings.auto_migrate:
        await run_migrations()
    start_scheduler()
    yield
    # 앱 종료 — 스케줄러 정상 종료
    stop_scheduler()


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(
        title="LingoLab Backend",
        version="0.1.0",
        description="AI 기반 일본어 학습 플랫폼의 백엔드",
        lifespan=lifespan,
    )

    # CORS — refresh 쿠키 전송을 위해 credentials 허용 + 명시적 origin
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # v1 라우터 등록
    app.include_router(health.router, prefix="/api/v1", tags=["health"])
    app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
    app.include_router(content.router, prefix="/api/v1/content", tags=["content"])
    app.include_router(study.router, prefix="/api/v1/study", tags=["study"])
    app.include_router(motivation.router, prefix="/api/v1/motivation", tags=["motivation"])

    # 호환용 루트 헬스 — 로드밸런서/CI probe 용
    @app.get("/healthz", tags=["health"])
    async def healthz() -> dict[str, str]:
        return {"status": "ok", "service": "backend", "version": app.version}

    return app


app = create_app()
