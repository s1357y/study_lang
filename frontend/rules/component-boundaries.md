# 컴포넌트 경계 규칙

## 디렉토리별 책임

### `src/app/`
- URL 이 필요한 페이지와 route handler 만.
- 페이지는 얇게 — 데이터 로딩(서버) + feature 컴포넌트 컴포지션만.
- 라우트 그룹: `(auth)` (사인인/사인업), `(app)` (보호된 영역).

### `src/features/<domain>/`
- 그 도메인의 비즈니스 컴포넌트, 훅, API 함수, 로컬 상태.
- **다른 feature 를 import 하지 않는다**. 공유 필요 시 `components/` 또는 `lib/` 로 승격.

### `src/components/ui/`
- 도메인 비종속 원자 컴포넌트 (Button, Card, Input).
- 도메인 훅(`useUser` 등) 사용 금지. 페이지/특정 API 에 의존 금지.

### `src/lib/`
- API 클라이언트 (`api/`), 인증 상태 (`auth/`), 공통 유틸 (`utils.ts`).
- 컴포넌트에서 직접 import 가능.

### `src/hooks/`
- 도메인 비종속 훅 (예: `useToast`, `useMediaQuery`).
- 도메인 훅은 해당 feature 디렉토리에.

## 새 파일 위치 결정 트리

1. URL 이 필요한 페이지? → `src/app/.../page.tsx`
2. 한 도메인에서만 쓰는 컴포넌트? → `src/features/<domain>/components/`
3. 어디서나 쓰는 UI? → `src/components/ui/`
4. 백엔드 호출? → `src/lib/api/backend.ts` 의 함수 추가 (모듈 분할은 도메인 수가 늘어나면)
5. 도메인 간 공유 타입? → `src/types/`
6. DB 직접 접근? → **금지**. 백엔드 API 추가 후 그것을 호출.
