# LingoLab Backend (FastAPI)

도메인/구조 정의는 [`STRUCTURE.md`](./STRUCTURE.md), 작업 규칙은 [`CLAUDE.md`](./CLAUDE.md), 전체 아키텍처는 [`../docs/architecture.md`](../docs/architecture.md) 참고.

## 로컬 실행

```bash
# 의존성 (uv 권장)
uv sync                                  # 또는 poetry install

# 환경 변수
cp ../.env.example ../.env               # 루트 .env 공유
# 또는 backend/.env 별도 작성

# Ollama / Postgres 가 떠 있는지 확인 (루트 docker-compose.yml)
docker compose -f ../docker-compose.yml ps

# 개발 서버
uv run uvicorn app.main:app --reload --port 8000
# → http://localhost:8000/docs
# → http://localhost:8000/healthz
# → http://localhost:8000/api/v1/health   (Ollama 체크 포함)
```

## 디렉토리 빠르게 보기

- `app/main.py` — FastAPI 진입점
- `app/api/v1/routes/` — 외부 HTTP 라우터
- `app/services/` — 비즈니스 로직
- `app/repositories/` — DB 접근 (SQLAlchemy)
- `app/llm/` — Ollama 호출 + 검증 + 프롬프트
- `app/workers/` — 백그라운드 작업 (콘텐츠 사전 생성 등)

## Phase 1 골격 검증

```bash
curl http://localhost:8000/healthz
# → {"status":"ok","service":"backend","version":"0.1.0"}

curl http://localhost:8000/api/v1/health
# → {"status":"ok",..., "checks": {"ollama": {...}}}
```
