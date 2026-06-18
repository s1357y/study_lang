# study-lang (LingoLab)

AI 기반 개인화 일본어 학습 플랫폼 MVP.

- **로컬 LLM(Ollama)** 이 학습 콘텐츠와 문제를 동적으로 생성
- **SRS(FSRS 알고리즘) + 약점 태그** 로 사용자 맞춤 출제
- **콘텐츠 풀 누적** — 한 번 생성된 콘텐츠는 재사용, 백그라운드 워커가 점진적으로 풀 보충
- **일일 학습 루프**: 신규 학습 + 과거 복습 자동 혼합
- **JLPT 형식 시험**: 배치 시험(첫 로그인) + 레벨업 시험(학습량 달성 시)
- **동기부여**: 스트릭 / XP / 주간 목표

## 모노레포 구성

```
study-lang/
├── frontend/           # Next.js 14+ App Router (TypeScript, Tailwind, TanStack Query)
├── backend/            # FastAPI (인증/DB/LLM/SRS/동기부여 단일 소유)
│   ├── app/            # 앱 소스 (routes → services → repositories → models)
│   ├── scripts/        # 운영 스크립트 (시딩, 마이그레이션, 보강)
│   ├── seeds/          # 초기 콘텐츠 데이터 (N2~N5 어휘, N3/N4 문법)
│   └── alembic/        # DB 마이그레이션
├── docs/               # 아키텍처, 도메인 모델, SRS, LLM, 인증 문서
└── docker-compose.yml  # postgres + ollama (로컬 개발용)
```

## 빠른 시작 (로컬 개발)

> 사전 요구: Docker Desktop, Node.js 20+, Python 3.11+, [uv](https://docs.astral.sh/uv/)

```powershell
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
uv run uvicorn app.main:app --reload --port 8001
# → http://localhost:8001/docs  (Swagger UI)
# → http://localhost:8001/healthz

# 5) 콘텐츠 시딩 (초기 어휘/문법 데이터 삽입)
#    어휘: N5~N2 전체 레벨
uv run python -m scripts.seed_content --level BEGINNER
uv run python -m scripts.seed_content --level ELEMENTARY
uv run python -m scripts.seed_content --level INTERMEDIATE
uv run python -m scripts.seed_content --level ADVANCED
#    문법: N4, N3 (grammar 시드 보유 레벨)
uv run python -m scripts.seed_content --level ELEMENTARY --kind grammar
uv run python -m scripts.seed_content --level INTERMEDIATE --kind grammar

# 6) MCQ_MEANING 오답 보강 (distractor 풀 6~9개 생성)
uv run python -m scripts.enrich_mcq_meaning --dry-run    # 대상 확인 (DB 변경 없음)
uv run python -m scripts.enrich_mcq_meaning               # 전체 실행 (distractors=NULL 대상)
uv run python -m scripts.enrich_mcq_meaning --upgrade     # 기존 3개짜리 레코드도 포함

# 7) 프론트엔드 실행 (별도 터미널)
cd frontend
npm install
npm run dev
# → http://localhost:3000
```

> **DB 마이그레이션**: `AUTO_MIGRATE=true` 설정이면 앱 기동 시 자동 실행.  
> 수동 적용: `uv run alembic upgrade head`

---

## 상황별 운영 명령어

### 콘텐츠 시딩

```powershell
cd backend

# 특정 레벨만 시딩
uv run python -m scripts.seed_content --level BEGINNER
uv run python -m scripts.seed_content --level ELEMENTARY
uv run python -m scripts.seed_content --level INTERMEDIATE
uv run python -m scripts.seed_content --level ADVANCED

# 문법 시딩 (ELEMENTARY=N4, INTERMEDIATE=N3 만 시드 보유)
uv run python -m scripts.seed_content --level ELEMENTARY --kind grammar
uv run python -m scripts.seed_content --level INTERMEDIATE --kind grammar

# 변경 없이 시딩 계획만 확인 (dry-run)
uv run python -m scripts.seed_content --level BEGINNER --dry-run
```

### MCQ_MEANING 오답 선택지 보강

MCQ_MEANING 문제에 의미 유사 오답을 LLM으로 6~9개 생성해 저장한다.
퀴즈 실행 시 그 중 3개를 `random.sample`로 선택 → 세션마다 다른 조합 노출.
멱등성 보장: `--upgrade` 없이 실행하면 이미 distractors가 있는 행은 자동 스킵.

```powershell
cd backend

# 대상 목록만 확인 (DB 변경 없음)
uv run python -m scripts.enrich_mcq_meaning --dry-run

# 전체 레벨 일괄 보강 (distractors=NULL 행만)
uv run python -m scripts.enrich_mcq_meaning

# 특정 레벨만
uv run python -m scripts.enrich_mcq_meaning --level BEGINNER
uv run python -m scripts.enrich_mcq_meaning --level ELEMENTARY

# 기존 3개짜리 레코드를 6~9개로 확장 (풀 업그레이드)
uv run python -m scripts.enrich_mcq_meaning --upgrade --dry-run   # 대상 확인
uv run python -m scripts.enrich_mcq_meaning --upgrade              # 전체 업그레이드
uv run python -m scripts.enrich_mcq_meaning --upgrade --level BEGINNER --batch-size 5

# 커밋 단위 조정 (기본 10)
uv run python -m scripts.enrich_mcq_meaning --batch-size 5
```

> **언제 실행해야 하나?**  
> - 초기 시딩 직후: `seed_content` → `enrich_mcq_meaning` 순서로 실행  
> - 기존 3개짜리 레코드를 6~9개로 확장하려면: `--upgrade` 플래그 추가  
> - 신규 LLM 생성 콘텐츠는 자동으로 6~9개 오답이 저장되므로 별도 실행 불필요

### DB 마이그레이션

```powershell
cd backend

# 최신 상태로 적용
uv run alembic upgrade head

# 현재 적용된 리비전 확인
uv run alembic current

# 마이그레이션 히스토리
uv run alembic history

# 모델 변경 후 신규 리비전 자동 생성
uv run alembic revision --autogenerate -m "설명"
```

### 개발 도구

```powershell
# 백엔드 린트
cd backend; python -m ruff check app/ scripts/

# 프론트엔드 타입 체크
cd frontend; npx tsc --noEmit

# pgAdmin (DB GUI) — tools 프로필 활성화 필요
docker compose --profile tools up -d
# → http://localhost:5050  (admin@studylang.local / admin)
```

### 서버 실행 (개발)

```powershell
# 백엔드 (hot-reload)
cd backend
uv run uvicorn app.main:app --reload --port 8001

# 프론트엔드 (hot-reload)
cd frontend
npm run dev
```

---

## 기술 스택

| 영역 | 기술 |
|------|------|
| 프론트엔드 | Next.js 14 (App Router), TypeScript, Tailwind CSS, TanStack Query v5, Zod |
| 백엔드 | FastAPI, SQLAlchemy 2.0 async, Alembic, Pydantic v2 |
| 데이터베이스 | PostgreSQL 16 (JSONB, ARRAY) |
| LLM | Ollama (로컬), Jinja2 프롬프트 템플릿 (`app/llm/prompts/*.j2`) |
| SRS | py-fsrs (FSRS 알고리즘) |
| 백그라운드 | APScheduler (콘텐츠 사전 생성 워커) |
| 인프라 | Docker Compose (postgres:16-alpine, ollama) |

---

## 구현 완료 범위

| Phase | 내용 |
|-------|------|
| 0 | Docker Compose 인프라 (postgres + ollama) |
| 1 | Next.js + FastAPI 프레임워크 골격 |
| 1.5 | 아키텍처 정리 (JWT 전환, Prisma 제거) |
| 2 | JWT 인증 (access token + HttpOnly refresh cookie rotation) |
| 3 | 콘텐츠 풀 & LLM 생성 파이프라인 (ContentItem → Problem 자동 생성) |
| — | Alembic 자동 마이그레이션 (앱 기동 시 적용) |
| 4 | SRS(FSRS) + 약점 태그 서비스 |
| 5 | 학습 세션 UI (StudyCard, MCQ/입력식, 결과 표시) |
| 6 | 동기부여 시스템 (스트릭, XP, 주간 목표) |
| 7 | 배치 시험 (레벨 자동 배정) + 학습 복습 (날짜별 이력) |
| 8 | 다중 문제 유형 (MCQ_GRAMMAR·MCQ_CONTEXT·MCQ_SYNONYM) + 문법 콘텐츠 생성 + N2~N5 어휘/문법 시드 |
| 9 | 학습 세션 연장 + LLM 폴백 + 배치고사 유형 혼합 (5문제×4레벨) + 레벨업 시험 (JLPT 형식, 20문제) |
| 10 | MCQ_MEANING 오답 다양화 — distractor 풀 6~9개 확장 + 세션마다 `random.sample(3)` + `--upgrade` 기존 레코드 재보강 |
| 11 | FILL_BLANK → MCQ 전환 (배치·레벨업·학습 세션 전체) + 전체 흐름 버그 수정 (SRS 상태 매핑 오류 감지, StudyError 전파, 캐시 무효화 완성, progress bar off-by-one, ProblemType 타입 동기화) |

---

## 시드 데이터 구성

| 파일 | 레벨 | 종류 | 항목 수 |
|------|------|------|---------|
| `seeds/vocabulary_n5.json` | BEGINNER (N5) | 어휘 | 52개 |
| `seeds/vocabulary_n4.json` | ELEMENTARY (N4) | 어휘 | 10개 |
| `seeds/vocabulary_n3.json` | INTERMEDIATE (N3) | 어휘 | 10개 |
| `seeds/vocabulary_n2.json` | ADVANCED (N2) | 어휘 | 10개 |
| `seeds/grammar_n4.json` | ELEMENTARY (N4) | 문법 | — |
| `seeds/grammar_n3.json` | INTERMEDIATE (N3) | 문법 | — |

> Phase 10부터 어휘 시드에 `confusable_meanings` 6~9개가 포함되어 있어  
> 시딩 즉시 의미 기반 MCQ_MEANING 오답이 생성됩니다.  
> 세션마다 그 중 3개를 `random.sample`로 선택해 매번 다른 조합이 출제됩니다.

---

## 학습 흐름 요약

```
[첫 로그인]
  └─ 배치 시험 → POST /api/v1/placement/problems
        레벨당 5문제 혼합 (MCQ_MEANING × 2 + MCQ_READING × 1 + MCQ_GRAMMAR × 1 + MCQ_CONTEXT × 1)
        총 20문제 → 채점 → User.level 자동 배정

[일일 학습]
  └─ POST /api/v1/study/sessions/today
        └─ SRS 복습 큐 + 신규 슬롯 혼합
  └─ 문제 풀기 → POST /api/v1/study/attempts
  └─ 완료 후 → POST /api/v1/study/sessions/today/extend (더 공부하기)
               풀 소진 시 LLM으로 신규 콘텐츠 자동 생성

[레벨업]
  └─ GET /api/v1/level-up/eligibility  (학습 30개+ 후 자격 확인)
  └─ GET /api/v1/level-up/problems     (JLPT 형식 20문제 발급)
  └─ POST /api/v1/level-up/submit      (70% 이상 시 User.level 승급, 미달 시 7일 쿨다운)
```

---

## 문서

| 문서 | 설명 |
|------|------|
| [`docs/architecture.md`](./docs/architecture.md) | 시스템 흐름도 및 컴포넌트 책임 |
| [`docs/auth-flow.md`](./docs/auth-flow.md) | access/refresh 토큰 + rotation 정책 |
| [`docs/data-model.md`](./docs/data-model.md) | 도메인 모델 (ERD) |
| [`docs/srs-algorithm.md`](./docs/srs-algorithm.md) | FSRS 알고리즘 설계 |
| [`docs/llm-strategy.md`](./docs/llm-strategy.md) | 콘텐츠 생성/재사용 정책 |
| [`docs/motivation-backlog.md`](./docs/motivation-backlog.md) | 동기부여 메커니즘 |
| [`docs/architecture/study-flow.md`](./docs/architecture/study-flow.md) | 학습 흐름 상세 (세션·레벨·SRS 불변식) |
| [`STRUCTURE.md`](./STRUCTURE.md) | 모노레포 전체 파일 구조 |
