# 작업 규칙 — study-lang (루트)

이 파일은 **인덱스**다. 세부 규칙은 링크된 파일에 있다. 하위 디렉토리(`frontend/`, `backend/`)에는 그 디렉토리만의 `CLAUDE.md`가 있으니 그쪽 작업 시 함께 따른다.

## 핵심 규칙

- **자동 커밋/푸시 금지** — 사용자가 명시적으로 요청할 때만. (자세히: [`docs/conventions/git-policy.md`](./docs/conventions/git-policy.md))
- **흐름 파악용 한국어 주석을 단다** — 줄 단위 X, 무주석 X. (자세히: [`docs/conventions/coding-comments.md`](./docs/conventions/coding-comments.md))
- **도메인 용어 일관성** — 모델명/엔드포인트/UI 모두 통일. (자세히: [`docs/conventions/terminology.md`](./docs/conventions/terminology.md))
- **CLAUDE.md 는 인덱스, 세부는 분리** — 200줄 미만 유지. 길어지면 `rules/<topic>.md` 로 즉시 분리.
- **구조 정의는 STRUCTURE.md 부터 본다** — 새 파일 위치는 STRUCTURE.md 의 결정 트리를 따른다.

## 아키텍처 단일 출처

- **DB 스키마**: `backend/app/models/` (SQLAlchemy) + `backend/alembic/versions/`. 프론트는 DB 에 직접 접근하지 않는다.
- **인증/토큰**: `backend/app/services/auth_service.py` 단일 소유. 프론트는 받아 쓰는 클라이언트. (자세히: [`docs/auth-flow.md`](./docs/auth-flow.md))
- **LLM 호출**: `backend/app/llm/client.py` 외 어디서도 Ollama 를 직접 호출하지 않는다.
- **API 경로**: 외부 노출은 모두 `/api/v1/...` 아래.
- **환경변수**: 루트 `.env.example` 에 등록한 다음 사용. 시크릿 노출 금지.

- **study-flow.md 갱신** — `study_service.py` · `srs_service.py` · `study_session_repo.py` · `level_up_service.py` · `useSubmitAttempt.ts` · `useStudySession.ts` 수정 시 [`docs/architecture/study-flow.md`](./docs/architecture/study-flow.md) 도 동기화.

## 도메인 개요

| 영역 | 위치 | 책임 |
|-----|-----|-----|
| 프론트엔드 | `frontend/` | UI, 사용자 인터랙션, 백엔드 API 호출 |
| 백엔드 | `backend/` | 인증, DB, LLM, SRS, 백그라운드 작업 |
| 인프라 | `docker-compose.yml` | postgres + ollama |
| 설계 문서 | `docs/` | 아키텍처/도메인/SRS/LLM/동기부여 |
