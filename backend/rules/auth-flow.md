# 인증 흐름 규칙 — backend

전체 정책은 [`/docs/auth-flow.md`](../../docs/auth-flow.md). 이 파일은 backend 가 지켜야 할 사항만.

## 단일 진입점

- 비밀번호 해시/검증: `core/security.hash_password` / `verify_password` (argon2id)
- JWT 인코딩/디코딩: `core/security.encode_access` / `encode_refresh` / `decode_*`
- 비즈니스 흐름: `services/auth_service.py` (`register`, `login`, `refresh`, `logout`)
- DB 접근: `repositories/refresh_token_repo.py`
- 라우터: `api/v1/routes/auth.py`

위 경계를 넘어서 직접 jwt 라이브러리나 argon2 를 호출하지 않는다.

## `auth_service.refresh` 의 검증 순서 (엄격)

1. JWT 서명·구조 검증 (`typ == "refresh"`)
2. DB 에서 `RefreshToken` 조회 (`id == jti`)
3. `token_hash == sha256(쿠키 평문)` 매칭
4. `revoked_at IS NULL` 검사 — **revoked 면 family 전체 revoke + 401 (reuse_detected)**
5. `expires_at > now()` 검사
6. 새 access + 새 refresh 발급 (같은 family, `parent_id = 이전 jti`)
7. 이전 token `revoked_at=now()`, `revoked_reason='rotated'`

## 쿠키 세팅

- `Set-Cookie: refresh_token=<jwt>; HttpOnly; SameSite=Lax; Path=/api/v1/auth; Max-Age=<refresh_ttl>`
- `Secure` 는 `settings.refresh_cookie_secure` (dev=false, prod=true)
- `Domain` 은 `settings.refresh_cookie_domain` (빈 문자열이면 host-only)

## 의존성 주입

- 보호 라우트는 `Depends(current_user_claims)` (access 토큰 검증만)
- 사용자 객체 자체가 필요하면 별도 의존성으로 DB 조회 (예: `current_user`)
- `current_user_claims` 안에서 DB 조회를 하지 않는다 (지연 최소화)

## FastAPI 204 + 쿠키 조작 패턴

204 No Content 응답에서 쿠키를 수정해야 할 때:

```python
# 올바른 패턴 — Response 를 파라미터로 주입, 반환값은 None
@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response, ...) -> None:
    ...
    response.delete_cookie(key="refresh_token", ...)
    # return 생략 (None implicit) — FastAPI 가 주입된 response 의 헤더를 최종 응답에 병합

# 잘못된 패턴 — 주입된 Response 를 직접 return 하면 비관용적이고 -> None 과 불일치
async def logout(...) -> Response:
    ...
    return response  # ❌
```

**왜**: FastAPI 의 `Response` 파라미터 주입 패턴에서 주입된 객체는 *헤더/쿠키 세팅용 사이드 채널*이다.
실제 HTTP 응답 본문/상태는 함수의 return 값(또는 None)으로 결정된다.
`return response` 는 FastAPI 가 raw Response 로 처리해 response_model/middleware 를 우회한다.

## 금지

- 평문 비밀번호 / refresh 토큰을 DB 에 저장 (해시만)
- 라우트에서 jwt 라이브러리 직접 사용
- `core/security` 외에서 `jwt.encode/decode` 호출
- access 토큰을 쿠키로 보내기 (응답 본문만)
- 204 라우트에서 주입된 `Response` 객체를 직접 `return`
