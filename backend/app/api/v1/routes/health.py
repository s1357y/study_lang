"""헬스 체크 — Ollama 도달성을 검증한다. DB 는 Phase 2에서 추가."""

from __future__ import annotations

from fastapi import APIRouter

from app.llm.client import LLMError, list_models

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, object]:
    # Ollama 모델 목록 조회로 도달성 확인 (LLM 계층 추상화 경유)
    checks: dict[str, object] = {}
    try:
        models = await list_models()
        checks["ollama"] = {"reachable": True, "models": models}
    except LLMError as exc:
        checks["ollama"] = {"reachable": False, "error": str(exc)}

    return {
        "status": "ok",
        "service": "backend",
        "version": "0.1.0",
        "checks": checks,
    }
