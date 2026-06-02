# Architecture

## 전체 흐름

```
┌────────────┐       ┌─────────────────┐       ┌───────────────┐       ┌───────────┐
│   Browser  │ ───▶  │  Next.js        │ ───▶  │  FastAPI      │ ───▶  │  Ollama   │
│  (사용자)   │ ◀───  │  (App Router)   │ ◀───  │  (인증/도메인) │ ◀───  │  (LLM)    │
└────────────┘       └─────────────────┘       └───────────────┘       └───────────┘
                                                        │
                                                        ▼
                                              ┌───────────────────┐
                                              │   PostgreSQL      │
                                              │  (SQLAlchemy owns │
                                              │   the schema)     │
                                              └───────────────────┘
                                                        ▲
                                                        │
                                              ┌─────────────────┐
                                              │  Background     │
                                              │  Worker (APS)   │
                                              │  콘텐츠 사전생성  │
                                              └─────────────────┘
```

## 컴포넌트 책임

| 컴포넌트 | 책임 |
|---------|-----|
| Next.js (frontend) | 라우팅, UI, 사용자 인증 폼 + 토큰 보관/재시도. **DB 직접 접근 금지** |
| FastAPI (backend) | **인증/토큰 발급/회전**, LLM 오케스트레이션, SRS, 약점 집계, 콘텐츠 풀, 일일 세션 |
| PostgreSQL | 영속 저장소. 스키마 소유는 SQLAlchemy + Alembic (backend) |
| Ollama | 로컬 LLM 추론. JSON 모드 구조화 출력 |
| Background Worker | 콘텐츠 풀 사전 생성, 약점 통계 주기적 재계산 |

## 인증 (요약)

```
사용자 → Next.js 사인인 폼
       → POST /api/v1/auth/login {email, password}  (백엔드 직접 호출)
       ← Response Body: {access_token, expires_in, user}
       ← Set-Cookie: refresh_token=...; HttpOnly; Secure; SameSite=Lax; Path=/api/v1/auth

프론트 → API 호출 시 Authorization: Bearer <access_token>
       → access 만료(401) → 자동 POST /api/v1/auth/refresh
                              (브라우저가 refresh 쿠키 자동 첨부, CORS credentials=include)
                           ← 새 access + 새 refresh (rotation)
```

전체 정책(재사용 감지, family tracking, 로그아웃)은 [`docs/auth-flow.md`](./auth-flow.md).

## 일일 학습 세션의 시퀀스

```
사용자 → POST /api/v1/sessions/today
         ↓
         backend:
           1) srs_service.due_today(user)        → 복습 카드 N개
           2) weakness_service.top_tags(user, k=5)
           3) content_service.fetch_new(user, level, focus_tags=...) → 신규 카드 M개
           4) 부족하면 generation_service.generate_async(...)
           5) 응답 {review: [...], new: [...]}
```

## 콘텐츠 사전 생성

별도 워커가 다음 조건에서 LLM 을 호출:
- (사용자 레벨 × 약점 태그) 조합의 콘텐츠 풀이 임계치 미만일 때
- 인기 태그의 콘텐츠 다양성이 낮을 때 (중복 감지)

생성물은 `validators.py` 를 통과한 것만 저장되며 품질 점수와 함께 정렬된다. 자세한 정책은 [`llm-strategy.md`](./llm-strategy.md).

## 환경별 쿠키/CORS 전제

### 로컬 개발 (localhost:3000 ↔ localhost:8000)
- 두 origin 은 port 만 다른 동일 host → 브라우저 입장에서 **same-site**
- refresh 쿠키: `SameSite=Lax; HttpOnly; Path=/api/v1/auth; Secure=false`
- CORS: `allow_origins=["http://localhost:3000"]`, `allow_credentials=True`

### 운영
- **권장**: 같은 등록 가능 도메인의 서브도메인 분리 (`app.lingolab.io` + `api.lingolab.io`)
  - refresh 쿠키 `Domain=.lingolab.io`, `Secure=true`, `SameSite=Lax`
  - CORS 는 `https://app.lingolab.io` 만 허용
- 도메인이 완전히 다르면 `SameSite=None; Secure=true` 필요 — 운영 시점 ADR 로 결정

## 배포 (향후)

MVP 단계 전제:
- 로컬 dev: `docker compose up` + Next.js `npm run dev` + FastAPI `uvicorn --reload`
- 운영 배포 결정은 별도 ADR (예: Vercel + Fly.io / Railway)
