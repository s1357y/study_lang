"""Ollama 호출의 단일 진입점. 다른 모듈은 이 함수만 사용한다.

진입점이 둘로 나뉜다:
- generate_json: 프롬프트를 보내 JSON 형식 응답을 받음 (콘텐츠 생성용)
- list_models: 현재 Ollama 서버가 보유한 모델 목록 (헬스체크/진단용)
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class LLMError(Exception):
    """Ollama 호출 실패 또는 응답 파싱 실패."""


async def generate_json(
    prompt: str,
    *,
    model: str | None = None,
    temperature: float = 0.4,
    timeout: float = 60.0,
) -> dict[str, Any]:
    # 모델은 settings 기본값을 사용하되 호출측이 오버라이드 가능
    chosen_model = model or settings.ollama_model
    payload = {
        "model": chosen_model,
        "prompt": prompt,
        "format": "json",  # Ollama 의 JSON 모드 강제
        "stream": False,
        "options": {"temperature": temperature},
    }
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(f"{settings.ollama_host}/api/generate", json=payload)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as exc:
        logger.warning("ollama request failed: %s", exc)
        raise LLMError(f"ollama request failed: {exc}") from exc

    raw_text = data.get("response", "")
    if not isinstance(raw_text, str):
        raise LLMError("ollama returned non-string response")

    # JSON 모드라도 마크다운/접두어가 섞일 수 있어 한 번 더 파싱 시도
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError as exc:
        logger.warning("ollama returned non-JSON: %s", raw_text[:200])
        raise LLMError("ollama returned non-JSON content") from exc


async def list_models(*, timeout: float = 2.0) -> list[str]:
    # 진단 목적의 가벼운 호출 — 실패하면 빈 리스트가 아니라 예외를 던지지 않고
    # 호출측에서 "도달 불가" 로 처리할 수 있도록 LLMError 만 발생시킨다.
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(f"{settings.ollama_host}/api/tags")
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as exc:
        raise LLMError(f"ollama unreachable: {exc}") from exc
    return [m.get("name") for m in data.get("models", []) if isinstance(m.get("name"), str)]
