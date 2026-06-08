# study-lang (LingoLab)

AI 기반 개인화 일본어 학습 플랫폼 MVP.

- **로컬 LLM(Ollama)** 이 학습 콘텐츠와 문제를 동적으로 생성
- **SRS(FSRS 알고리즘) + 약점 태그** 로 사용자 맞춤 출제
- **콘텐츠 풀 누적** — 한 번 생성된 콘텐츠는 재사용, 백그라운드 워커가 점진적으로 풀 보충
- **일일 학습 루프**: 신규 학습 + 과거 복습 자동 혼합
- **동기부여**: 스트릭 / XP / 주간 목표

## 모노레포 구성

```
study-lang/
├── frontend/           # Next.js 14+ App Router (TypeScript, Tailwind, TanStack Query)
├── backend/            # FastAPI (인증/DB/LLM/SRS/동기부여 단일 소유)
├── docs/               # 아키텍처, 도메인 모델, SRS, LLM, 인증 문서
└── docker-compose.yml  # postgres + ollama (로컬 개발용)
```

## 빠른 시작 (로컬 개발)

> 사전 요구: Docker Desktop, Node.js 20+, Python 3.11+, [uv](https://docs.astral.sh/uv/)

```bash
# 1) 환경변수 설정
cp .env.example .env
# .env 파일을 열어 필요한 값 입력

# 2) 인프라 실행 (postgres + ollama)
docker compose up -d

# 3) Ollama 모델 다운로드
docker exec -it study-lang-ollama ollama pull qwen2.5:7b-instruct

# 4) 백엔드 실행 (DB 마이그레이션 자동 적용)
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 8000
# → http://localhost:8000/docs  (Swagger UI)
# → http://localhost:8000/healthz

# 5) 콘텐츠 시딩 (선택 — 초기 어휘 데이터 삽입)
uv run python -m scripts.seed_content

# 6) 프론트엔드 실행 (별도 터미널)
cd frontend
npm install
npm run dev
# → http://localhost:3000
```

> DB 마이그레이션은 앱 기동 시 `AUTO_MIGRATE=true` 설정이면 자동 실행됩니다.  
> 수동으로 적용하려면: `uv run alembic upgrade head`

## 기술 스택

| 영역 | 기술 |
|------|------|
| 프론트엔드 | Next.js 14 (App Router), TypeScript, Tailwind CSS, TanStack Query, Zod |
| 백엔드 | FastAPI, SQLAlchemy 2.0 async, Alembic, Pydantic v2 |
| 데이터베이스 | PostgreSQL (JSONB, ARRAY) |
| LLM | Ollama (로컬), Jinja2 프롬프트 템플릿 |
| SRS | py-fsrs (FSRS 알고리즘) |
| 백그라운드 | APScheduler (콘텐츠 사전 생성 워커) |
| 인프라 | Docker Compose |

## 구현 완료 범위

| Phase | 내용 |
|-------|------|
| 0 | docker-compose 인프라 (postgres + ollama) |
| 1 | Next.js + FastAPI 프레임워크 골격 |
| 1.5 | 아키텍처 정리 (JWT 전환, Prisma 제거) |
| 2 | JWT 인증 (access token + HttpOnly refresh cookie rotation) |
| 3 | 콘텐츠 풀 & LLM 생성 파이프라인 (ContentItem → Problem 자동 생성) |
| — | Alembic 자동 마이그레이션 (앱 기동 시 적용) |
| 4 | SRS(FSRS) + 약점 태그 서비스 |
| 5 | 학습 세션 UI (StudyCard, MCQ/입력식, 결과 표시) |
| — | N5 어휘 시드 데이터 |
| 6 | 동기부여 시스템 (스트릭, XP, 주간 목표) |

## 문서

- [`docs/architecture.md`](./docs/architecture.md) — 시스템 흐름도 및 컴포넌트 책임
- [`docs/auth-flow.md`](./docs/auth-flow.md) — access/refresh 토큰 + rotation 정책
- [`docs/data-model.md`](./docs/data-model.md) — 도메인 모델 (ERD)
- [`docs/srs-algorithm.md`](./docs/srs-algorithm.md) — FSRS 알고리즘 설계
- [`docs/llm-strategy.md`](./docs/llm-strategy.md) — 콘텐츠 생성/재사용 정책
- [`docs/motivation-backlog.md`](./docs/motivation-backlog.md) — 동기부여 메커니즘
- [`STRUCTURE.md`](./STRUCTURE.md) — 모노레포 전체 파일 구조
