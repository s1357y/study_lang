# study-lang (LingoLab)

AI 기반 개인화 언어 학습 플랫폼. 1차 MVP 는 일본어를 대상으로 한다.

- **로컬 LLM(Ollama)** 이 학습 콘텐츠와 문제를 동적으로 생성
- **SRS(간격 반복) + 약점 태그** 로 사용자 맞춤 출제
- **콘텐츠 풀 누적** — 한 번 생성된 콘텐츠는 재사용, 새 콘텐츠는 백그라운드에서 점진 생성
- **일일 학습 루프**: 신규 학습 + 과거 복습 자동 혼합
- **동기부여**: 스트릭 / XP / 주간 목표

## 모노레포 구성

```
study-lang/
├── frontend/   # Next.js 14+ App Router (TypeScript, Tailwind)
├── backend/    # FastAPI (인증/스키마/LLM/SRS의 단일 소유자)
├── docs/       # 아키텍처/도메인/SRS/LLM/인증 문서
└── docker-compose.yml  # postgres + ollama (로컬 개발용)
```

전체 구조의 설계 의도는 [`STRUCTURE.md`](./STRUCTURE.md), 작업 규칙은 [`CLAUDE.md`](./CLAUDE.md) 참고.

## 빠른 시작 (로컬 개발)

> 사전 요구: Docker Desktop, Node.js 20+, Python 3.11+, [uv](https://docs.astral.sh/uv/) 또는 Poetry.

```bash
# 1) 인프라 실행 (postgres + ollama)
cp .env.example .env
docker compose up -d

# 2) Ollama 모델 다운로드 (Phase 0 sanity check)
docker exec -it study-lang-ollama ollama pull qwen2.5:7b-instruct

# 3) 백엔드 (DB 마이그레이션 + 서버 기동)
cd backend
uv sync                           # 또는 poetry install
uv run alembic upgrade head       # Phase 2 에서 모델 추가 후 사용
uv run uvicorn app.main:app --reload --port 8000
# → http://localhost:8000/docs
# → http://localhost:8000/healthz
# → http://localhost:8000/api/v1/health

# 4) 프론트엔드 (별도 터미널)
cd frontend
npm install
npm run dev                       # → http://localhost:3000
```

## 문서

- [`STRUCTURE.md`](./STRUCTURE.md) — 모노레포 전체 구조 정의
- [`CLAUDE.md`](./CLAUDE.md) — 작업 규칙 (인덱스)
- [`docs/architecture.md`](./docs/architecture.md) — 시스템 흐름도
- [`docs/auth-flow.md`](./docs/auth-flow.md) — access/refresh 토큰 + rotation 정책
- [`docs/data-model.md`](./docs/data-model.md) — 도메인 모델
- [`docs/srs-algorithm.md`](./docs/srs-algorithm.md) — SRS(FSRS) 설계
- [`docs/llm-strategy.md`](./docs/llm-strategy.md) — 콘텐츠 생성/재사용 정책
- [`docs/motivation-backlog.md`](./docs/motivation-backlog.md) — 동기부여 메커니즘 후보
- [`docs/conventions/`](./docs/conventions) — 공통 컨벤션 (주석 스타일, 용어, git 정책)

## 진행 상태

현재 단계: **Phase 1.5 정리 완료**. Phase 2 (백엔드 단일 소유 인증) 진입 대기.
계획 파일은 `~/.claude/plans/polymorphic-honking-lecun.md` 참고.
