# API 클라이언트 규칙

## 단일 진입점

모든 백엔드 호출은 `src/lib/api/backend.ts` 의 함수를 거친다. 컴포넌트나 features 모듈에서 `fetch` 를 직접 부르지 않는다.

## 클라이언트 책임 (Phase 2 이후 완성형)

1. 백엔드 base URL 주입 (`NEXT_PUBLIC_BACKEND_URL`)
2. `Authorization: Bearer <access>` 자동 첨부
3. `credentials: "include"` — refresh 쿠키가 cross-origin 요청에 따라가도록
4. 401 응답 시 자동 `/auth/refresh` 후 재시도
5. 동시 401 들은 **단일 refresh Promise** 로 큐잉 (race 방지)
6. refresh 실패 시 인증 상태 클리어 + 로그인 페이지로 이동

## 응답 검증

- 가능하면 응답을 zod 스키마로 한 번 더 검증 (백엔드는 신뢰하지만 런타임 가드).
- 도메인별 함수로 노출 (`fetchTodaySession()`, `submitAttempt(...)` 등) — 컴포넌트는 함수만 호출.

## 타입 단언(`as`) 금지 — 런타임 가드 사용

외부에서 오는 데이터(백엔드 응답, 에러 상세)에 `as SomeType` 단언을 쓰지 않는다.
TypeScript `as` 는 컴파일 타임 체크만 통과시키며, 런타임에서 잘못된 형태가 들어오면 조용히 깨진다.

```typescript
// 나쁜 예 — as 로 구조를 가정, 런타임 검증 없음
const detail = (err.detail as { detail?: string })?.detail;

// 좋은 예 — 실제 타입을 확인한 뒤 접근
const raw = err.detail;
const message =
  raw !== null &&
  typeof raw === "object" &&
  "detail" in raw &&
  typeof (raw as Record<string, unknown>).detail === "string"
    ? (raw as { detail: string }).detail
    : null;
```

**적용 기준**
- 백엔드 응답 JSON → 타입: `zod.parse()` 또는 위 패턴의 guard 체인.
- `ApiError.detail` 접근 시: 항상 런타임 타입 가드.
- 내부에서 이미 타입이 보장된 값: `as` 허용 (예: `undefined as unknown as T` 의 204 처리 등).

## React Query

- 호출은 `@tanstack/react-query` 의 `useQuery` / `useMutation` 으로 감싼다.
- 쿼리 키 컨벤션: `[domain, action, ...params]` (예: `["session", "today"]`)
- `staleTime` 은 도메인 특성에 맞게 (학습 세션은 짧게, 사용자 프로필은 길게).
