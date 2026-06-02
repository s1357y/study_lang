# 인증 흐름 — Access / Refresh + Rotation

## 원칙

1. **백엔드가 인증/토큰의 단일 소유자**. 프론트엔드는 토큰을 받아 쓰는 클라이언트.
2. **이중 토큰 패턴**:
   - access token: 짧은 수명 JWT(15분). 응답 본문 → 프론트 **메모리**(상태) 보관.
   - refresh token: 긴 수명 JWT(30일). **HttpOnly + SameSite=Lax + Path 제한 쿠키**.
3. **Refresh token rotation**: 매 갱신마다 새 refresh 발급, 이전 것은 DB에서 revoke.
4. **Family tracking**: 동일 로그인 세션의 refresh 들은 같은 `family_id` 를 공유. 재사용 감지 시 family 전체 폐기.
5. **비밀번호는 argon2id**. 평문 저장/로깅 금지.

## 토큰 구조

### Access JWT (HS256)
```json
{ "sub": "<user_id>", "iat": ..., "exp": ..., "typ": "access" }
```

### Refresh JWT (HS256)
```json
{ "sub": "<user_id>", "jti": "<uuid>", "fid": "<family_id>", "iat": ..., "exp": ..., "typ": "refresh" }
```

- `jti` = 이 refresh 의 고유 id. DB `RefreshToken.id` 와 매칭.
- `fid` = family id. 동일 family 의 모든 refresh 가 공유.

## 데이터베이스 — `RefreshToken`

```
id          UUID  (== jti)
user_id     UUID  (FK → User)
token_hash  TEXT  (sha256(refresh_jwt) — 평문 토큰은 저장 안 함)
family_id   UUID
parent_id   UUID  (이전 토큰의 id, NULL = 로그인으로 새로 시작된 family)
issued_at   TIMESTAMPTZ
expires_at  TIMESTAMPTZ
revoked_at  TIMESTAMPTZ  (NULL = 활성)
revoked_reason TEXT  ("rotated" | "logout" | "reuse_detected" | "manual")
```

인덱스: `(user_id, family_id, revoked_at)`

## 흐름별 절차

### 1. 회원가입 / 로그인
1. 비밀번호 argon2 검증
2. 새 `family_id` 생성
3. access + refresh JWT 발급 (refresh 는 `parent_id=NULL`)
4. `RefreshToken` row 생성 (`id=jti`, `token_hash=sha256(refresh)`)
5. 응답:
   - 본문: `{ access_token, expires_in, user }`
   - `Set-Cookie: refresh_token=<jwt>; HttpOnly; Secure; SameSite=Lax; Path=/api/v1/auth; Max-Age=<refresh_ttl>`

### 2. 보호 엔드포인트 호출
- 프론트: `Authorization: Bearer <access>`
- 백엔드: access JWT 서명·만료 검증 → `current_user` 주입
- 만료 시 401 반환

### 3. Refresh
1. 프론트 401 감지 → `POST /api/v1/auth/refresh` (브라우저가 refresh 쿠키 자동 첨부)
2. 백엔드 검증 **순서**:
   1. JWT 서명·구조 검증 (`typ == "refresh"`)
   2. DB 에서 `RefreshToken` 조회 (`id == jti`)
   3. `token_hash == sha256(쿠키)` 매칭
   4. `revoked_at` 검사 → **NULL 이 아니면 재사용 → family 전체 revoke + 401 (reuse_detected)**
   5. `expires_at` 검사 → 만료면 401
3. 회전 발급:
   - 새 jti 로 access + refresh 발급, 같은 `family_id` 유지, `parent_id = 이전 jti`
   - 이전 token: `revoked_at=now()`, `revoked_reason="rotated"`
4. 응답: 새 access(본문) + 새 refresh(쿠키)

### 4. 로그아웃
- `POST /api/v1/auth/logout` → 해당 family 전체를 `revoked_reason="logout"` 으로 revoke
- 응답에 `Set-Cookie: refresh_token=; Max-Age=0` 으로 쿠키 삭제 지시

### 5. 재사용 감지 시
- 클라이언트가 이미 회전된 refresh 를 다시 제출 → 침해 가능성
- 동일 family 의 모든 활성 token 을 `revoked_reason="reuse_detected"` 로 revoke
- 사용자는 다시 로그인해야 함

## 프론트엔드 처리 패턴

### Access 토큰 저장
- React Context 또는 Zustand 의 **메모리 상태**에만 보관 (localStorage 금지 — XSS 방어)
- 페이지 새로고침 / 새 탭 진입 시: 즉시 `/auth/refresh` 호출로 access 복구
  - 성공 → 인증 상태 진입
  - 실패 → 로그인 페이지로 리다이렉트

### 401 자동 재시도 + race 방지
```typescript
let inflightRefresh: Promise<void> | null = null;

async function fetchWithAuth(input, init) {
  let res = await rawFetch(input, withAccess(init));
  if (res.status !== 401) return res;
  // 동시 401 들이 모두 단일 refresh 를 공유해야 race 가 없다
  inflightRefresh ??= doRefresh().finally(() => { inflightRefresh = null; });
  await inflightRefresh;
  res = await rawFetch(input, withAccess(init));
  return res;
}
```

## MVP 미구현 (백로그)

- 이메일 인증 (`email_verified_at` 컬럼만 두고 NULL)
- 비밀번호 재설정
- IP / 사용자 단위 rate limiting (`/login`, `/register`, `/refresh`)
- 전체 디바이스 로그아웃 (사용자의 모든 family revoke)
- 재사용 감지 시 사용자 알림 UI
- OAuth 소셜 로그인
