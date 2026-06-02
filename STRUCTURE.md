# Repository Structure — study-lang

이 문서는 **이 모노레포가 왜 이렇게 나뉘어 있는지**와 **새 파일/모듈을 추가할 때 어디에 두어야 하는지**를 정의한다. 각 하위 프로젝트의 내부 구조는 해당 디렉토리의 `STRUCTURE.md` 참고.

## 디렉토리 한눈에

```
study-lang/
├── frontend/          # Next.js 14+ App Router 웹 앱
├── backend/           # FastAPI — 인증/스키마/LLM의 단일 소유자
├── docs/              # 시스템 설계 문서 (코드 비종속)
│   └── conventions/   # 전역 컨벤션 (CLAUDE.md 에서 링크)
├── docker-compose.yml # 로컬 인프라 (postgres, ollama)
├── .env.example       # 모든 환경변수의 단일 출처
├── STRUCTURE.md       # ← 이 파일
├── CLAUDE.md          # 루트 작업 규칙 (인덱스)
└── README.md
```

## 분리 원칙

### 왜 frontend / backend 를 분리했는가

- **LLM/ML 파이프라인을 Python 생태계로 다루기 위함**. Ollama 클라이언트, FSRS, 토크나이저/검증, 백그라운드 워커는 Python 이 가장 자연스럽다.
- **인증을 백엔드가 단일 소유**. 토큰 발급/검증/회전 모두 FastAPI 가 책임. 프론트는 토큰을 받아 쓰는 클라이언트.
- **수평 확장 패턴이 다르다**. 프론트는 SSR/엣지, 백엔드는 LLM·워커 큐 — 배포 단위를 나누는 편이 유리.

### 왜 모노레포인가

- 도메인 모델/API 계약 변경 시 양쪽을 함께 수정해야 한다. 분리 리포지토리는 동기화 비용만 늘린다.
- 빌드/배포 파이프라인은 각각 독립 가능하므로 모노레포의 단점이 없다.

## 스키마의 단일 출처 (Single Source of Truth)

**DB 스키마의 단일 출처는 `backend/app/models/` (SQLAlchemy) + Alembic 마이그레이션**이다.

- 모델 정의: `backend/app/models/<entity>.py`
- 마이그레이션: `backend/alembic/versions/`
- 새 컬럼/테이블은 항상 SQLAlchemy 모델에 먼저 추가 → `alembic revision --autogenerate` → 검토 후 커밋
- 자세한 절차는 [`backend/rules/schema-migrations.md`](./backend/rules/schema-migrations.md)

프론트엔드는 DB 에 직접 접근하지 않는다. 모든 데이터는 백엔드 API 경유.

## frontend ↔ backend 계약

- **인증**: 백엔드가 access(메모리) + refresh(HttpOnly 쿠키) 발급. 프론트는 `Authorization: Bearer <access>` 헤더로 호출. 401 시 자동 `/auth/refresh`. (자세히: [`docs/auth-flow.md`](./docs/auth-flow.md))
- **API base URL**: 프론트는 `NEXT_PUBLIC_BACKEND_URL` 환경변수로 백엔드 주소를 안다.
- **API 버저닝**: 모든 외부 노출 엔드포인트는 `/api/v1/...` 아래.
- **데이터 형식**: JSON. 날짜는 ISO 8601 UTC.
- **CORS**: 백엔드는 `allow_origins=[<frontend-origin>]`, `allow_credentials=True`. `*` 와일드카드 금지 (credentials 와 양립 불가).

## 새 파일을 추가할 때 — 결정 트리

1. UI 컴포넌트나 페이지인가? → `frontend/src/...` (상세는 `frontend/STRUCTURE.md`)
2. 도메인 로직(LLM 호출, SRS, 약점 집계, 인증, DB)인가? → `backend/app/...` (상세는 `backend/STRUCTURE.md`)
3. 코드와 무관한 설계 결정/가이드인가? → `docs/`
4. 두 프로젝트가 모두 참조하는 컨벤션인가? → `docs/conventions/`
5. 두 프로젝트 공유 타입? → **현재 단계는 양쪽 수동 미러링**. 5개 이상 누적되면 `packages/shared-types/` 도입 ADR.

## 환경변수

- 단일 출처는 루트 `.env.example`. 개별 `.env` 는 각 프로젝트에서 로드한다.
- 프론트는 `NEXT_PUBLIC_*` 접두어로 클라이언트 노출. 그 외는 서버 전용.
- 시크릿은 절대 커밋하지 않는다.

## 문서의 위치

| 문서 종류 | 위치 |
|----------|-----|
| 시스템 전체 흐름/도메인/정책 | `docs/` |
| 모노레포 공통 컨벤션 | `docs/conventions/` |
| 모노레포 구조 정의 | 루트 `STRUCTURE.md` |
| 모노레포 작업 규칙 (인덱스) | 루트 `CLAUDE.md` |
| 각 프로젝트 내부 구조 | `frontend/STRUCTURE.md`, `backend/STRUCTURE.md` |
| 각 프로젝트 작업 규칙 (인덱스) | `frontend/CLAUDE.md`, `backend/CLAUDE.md` |
| 각 프로젝트 세부 규칙 | `<project>/rules/*.md` |
| ADR | `docs/adr/NNNN-title.md` (3개째 ADR 이 나올 때 폴더 신설) |

## 향후 확장

- 모바일 앱이 추가될 경우 `mobile/` 디렉토리를 같은 레벨에 둔다.
- 다국어 학습 지원 확장 시 콘텐츠 풀 격리 전략(컬럼 vs 테이블)은 ADR로 결정한다.
