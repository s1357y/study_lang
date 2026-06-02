# Frontend Structure — Next.js (App Router)

## 디렉토리

```
frontend/
├── CLAUDE.md             # 작업 규칙 (인덱스)
├── STRUCTURE.md          # ← 이 파일
├── rules/                # CLAUDE.md 에서 링크되는 세부 규칙
│   ├── api-client.md
│   ├── auth-flow.md
│   └── component-boundaries.md
├── package.json
├── tsconfig.json
├── next.config.mjs
├── tailwind.config.ts
├── postcss.config.mjs
└── src/
    ├── app/              # App Router 라우트
    │   ├── layout.tsx
    │   ├── page.tsx
    │   ├── globals.css
    │   ├── (auth)/       # 사인인/사인업
    │   │   ├── sign-in/page.tsx
    │   │   └── sign-up/page.tsx
    │   └── (app)/        # 보호 영역
    │       ├── layout.tsx       # 클라이언트 인증 가드 (MVP)
    │       ├── dashboard/page.tsx
    │       ├── study/page.tsx
    │       └── review/page.tsx
    ├── components/       # 도메인 비종속 재사용 UI (shadcn 기반)
    │   └── ui/
    ├── features/         # 도메인 모듈
    │   ├── auth/
    │   ├── study/
    │   ├── review/
    │   ├── profile/
    │   └── motivation/
    ├── lib/
    │   ├── api/          # backend.ts: 토큰 첨부 + 401 시 refresh 큐잉
    │   ├── auth/         # access 메모리 상태, 로그아웃 헬퍼
    │   └── utils.ts
    ├── hooks/            # 공통 hooks
    ├── types/            # 글로벌 타입
    └── styles/           # 글로벌 스타일 (테마 토큰)
```

## 분리 원칙

### `app/` vs `features/` vs `components/`
경계 정의는 [`rules/component-boundaries.md`](./rules/component-boundaries.md).

### `app/(auth)` vs `app/(app)`
- Route Group 으로 인증 전/후 레이아웃 분리.
- `(app)/layout.tsx` 가 인증 가드 (MVP 는 `"use client"`).

### 인증 / API 클라이언트
- 토큰 흐름은 [`rules/auth-flow.md`](./rules/auth-flow.md).
- 백엔드 호출 패턴은 [`rules/api-client.md`](./rules/api-client.md).

## DB 접근 정책

- 프론트엔드는 **데이터베이스에 직접 접근하지 않는다**. ORM 의존성 없음.
- 모든 데이터는 백엔드 `/api/v1/...` 경유.
- 스키마 단일 출처는 `backend/app/models/` (SQLAlchemy).

## 환경변수

`process.env.*` 직접 접근 금지. `src/lib/env.ts` (도입 예정) 에서 zod 검증된 객체를 import. 클라이언트 노출 변수는 `NEXT_PUBLIC_` 접두어 필수.

## 테스트 (Phase 5+)

- 컴포넌트 테스트: Vitest + Testing Library
- E2E: Playwright
- 테스트 파일은 대상과 동일 디렉토리에 `*.test.ts(x)` 로 (co-location).
