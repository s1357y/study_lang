# 인증 흐름 — 프론트엔드 측

전체 정책은 [`/docs/auth-flow.md`](../../docs/auth-flow.md). 이 파일은 프론트엔드가 지켜야 할 사항만 요약.

## 토큰 보관

- **access**: React Context (또는 Zustand) 의 **메모리 상태**. `localStorage` / `sessionStorage` 금지 (XSS 방어).
- **refresh**: 백엔드가 세팅한 HttpOnly 쿠키. JS 에서 접근 불가. 직접 다루지 않는다.

## 부팅 시 흐름

1. 앱 진입 → `/auth/refresh` 1회 호출
2. 200 → access 를 메모리에 저장 + 인증 상태 진입
3. 401 → 로그인 페이지로 리다이렉트

## 보호 라우트

- MVP 단계: `(app)/layout.tsx` 를 `"use client"` 로 두고 클라이언트에서 인증 상태 검사
- 인증 미완료 동안 로딩 스켈레톤 표시
- 서버 컴포넌트 + 쿠키 forwarding 패턴은 Phase 5+ 에서 필요해지면 ADR

## API 호출 흐름

- `lib/api/backend.ts` 가 자동 처리 — 컴포넌트는 인증을 의식하지 않는다.
- 401 → `/auth/refresh` 큐잉 → 재시도. 자세히 [`api-client.md`](./api-client.md).

## 로그아웃

- `POST /api/v1/auth/logout` 호출 → 메모리의 access 클리어 → 사인인 페이지로 이동
- 백엔드가 family 전체 revoke + refresh 쿠키 삭제 응답을 보냄

## 금지

- access 토큰을 `localStorage` 에 저장
- refresh 토큰을 JS 로 읽으려는 시도 (HttpOnly 이므로 불가능)
- 401 발생 시 raw 한 번 더 호출 (반드시 클라이언트 함수 거치기)
