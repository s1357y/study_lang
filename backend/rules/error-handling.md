# 에러 처리 규칙 — backend

## 예외 계층 완전 포착

라이브러리 예외를 catch 할 때 **문서에 나온 베이스 예외 하나만 잡지 않는다.**  
라이브러리는 같은 상황을 여러 예외 클래스로 분류하며, 미처리 예외는 500으로 노출된다.

**패턴**
```python
# 나쁜 예 — VerifyMismatchError 만 잡으면 InvalidHashError 는 500 이 됨
try:
    return hasher.verify(hashed, plain)
except VerifyMismatchError:
    return False

# 좋은 예 — 같은 시맨틱(검증 실패)을 가진 예외 계열을 모두 포함
try:
    return hasher.verify(hashed, plain)
except (VerifyMismatchError, InvalidHashError):
    return False
```

**적용 기준**
- 라이브러리 예외를 catch 할 때: 라이브러리 문서/소스에서 같은 상황에 던질 수 있는 예외 계열을 모두 확인한다.
- 서비스 경계 (routes, services): 내부 예외가 외부로 새지 않도록 도메인 예외(`AuthError` 등)로 감싸 반환한다.
- **catch-all `except Exception`은 금지** — 범위가 너무 넓다. 필요한 예외 클래스를 명시적으로 나열한다.

## 경계에서만 검증

- **외부 입력 (HTTP 요청 본문, 쿠키, JWT 클레임)**: 라우터 또는 서비스 진입부에서 즉시 검증.
- **내부 호출 (repo → service, service → route)**: 이미 검증된 데이터이므로 방어적 검증 중복 금지.
- DB 손상 등 **비정상 상태 (데이터 신뢰 불가)**는 별도 예외 분기로 처리하되 운영 로그를 남긴다.

## HTTP 상태 코드 매핑

도메인 예외 → HTTP 상태 변환은 **라우터 레이어에서만** 한다. 서비스/리포는 도메인 예외만 던진다.

```python
# auth.py (route) 에서만 HTTP 매핑
def _auth_error_to_http(exc: AuthError) -> HTTPException:
    if exc.code == "email_taken":
        return HTTPException(409, detail=str(exc))
    return HTTPException(401, detail=str(exc))
```
