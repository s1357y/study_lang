# 작업 규칙 — frontend

이 파일은 **인덱스**다. 루트 [`CLAUDE.md`](../CLAUDE.md) 를 먼저 따른다. 세부 규칙은 [`rules/`](./rules) 의 개별 파일에 있다.

## 핵심 규칙

- **App Router 만 사용** — `pages/` 디렉토리 추가 금지.
- **컴포넌트 경계 준수** — 결정 트리는 [`rules/component-boundaries.md`](./rules/component-boundaries.md).
- **API 호출은 반드시 `lib/api/backend.ts` 경유** — 컴포넌트에서 raw `fetch` 금지. (자세히: [`rules/api-client.md`](./rules/api-client.md))
- **인증 토큰 처리** — access 는 메모리, refresh 는 쿠키 자동. (자세히: [`rules/auth-flow.md`](./rules/auth-flow.md))
- **DB 직접 접근 금지** — 모든 데이터는 백엔드 API 경유. 프론트엔드에는 ORM 의존성이 없다.

## 기본 컨벤션

- 클라이언트 컴포넌트가 필요할 때만 `"use client"` 명시. 기본은 서버 컴포넌트.
- Tailwind 클래스 우선. 인라인 스타일/별도 CSS 금지 (글로벌 토큰 제외).
- 디자인 토큰은 `tailwind.config.ts` 의 `theme.extend` 에 등록.
- UI 텍스트는 한국어 우선. 모듈 상단 상수로 분리해 향후 i18n 추출 용이하게.

## 금지

- `pages/` 디렉토리 추가
- 컴포넌트에서 raw `fetch` 직접 호출
- access 토큰을 `localStorage` 등 영구 저장소에 보관
- 시크릿 클라이언트 노출 (`NEXT_PUBLIC_*` 외 변수의 클라이언트 사용)
