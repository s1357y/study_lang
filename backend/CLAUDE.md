# 작업 규칙 — backend

이 파일은 **인덱스**다. 루트 [`CLAUDE.md`](../CLAUDE.md) 를 먼저 따른다. 세부 규칙은 [`rules/`](./rules) 의 개별 파일에 있다.

## 핵심 규칙

- **계층 경계 준수** — routes → services → repositories → models. (자세히: [`rules/layer-boundaries.md`](./rules/layer-boundaries.md))
- **인증 흐름은 단일 진입점** — `auth_service` + `core/security`. (자세히: [`rules/auth-flow.md`](./rules/auth-flow.md))
- **LLM 호출은 `llm/client.py` 외 어디에서도 하지 않는다** — 프롬프트는 `llm/prompts/` 템플릿. (자세히: [`rules/llm-calls.md`](./rules/llm-calls.md))
- **스키마는 SQLAlchemy + Alembic 단일 출처** — 마이그레이션은 autogenerate. (자세히: [`rules/schema-migrations.md`](./rules/schema-migrations.md))
- **에러 처리** — 라이브러리 예외 계층 완전 포착, 경계 검증 패턴. (자세히: [`rules/error-handling.md`](./rules/error-handling.md))

## 기본 컨벤션

- FastAPI 라우트 핸들러는 `async def` 기본. CPU 바운드만 동기.
- DB 는 SQLAlchemy 2.0 async 세션. HTTP 는 `httpx.AsyncClient`.
- 설정/시크릿 접근은 `core/config.py` 의 `Settings` 객체만. `os.environ` 직접 금지.
- 보호 라우트는 `Depends(current_user_claims)` 로 사용자 주입.
- 로깅은 `core/logging.py` 의 logger. `print` 금지.

## 금지

- routes 에서 raw SQL 또는 SQLAlchemy 쿼리 직접 호출
- services 에서 `httpx` 직접 호출 (LLM 은 `client.py` 경유)
- 새 시크릿을 `.env.example` 에 등록하지 않고 도입
- 프롬프트를 인라인 문자열로 (반드시 `llm/prompts/*.j2`)
