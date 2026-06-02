# 코드 주석 컨벤션

이 프로젝트는 코드의 **흐름을 파악할 수 있는 수준의 한국어 주석**을 요구한다. 줄 단위 설명도, 주석 없는 코드도 둘 다 거부한다.

## 원칙

1. **블록/함수 단위 의도 주석** — "이 함수가 *왜* 이렇게 하는지" 한 줄.
2. **줄 단위 설명 금지** — 식별자/타입이 충분히 말한다면 주석 추가 금지.
3. **한국어 기본** — 식별자는 영어, 주석은 한국어.

## 어떤 경우에 주석을 다는가

- 함수 진입부: 한 줄 의도 (docstring 보다 짧게)
- 5줄 이상의 단일 흐름 함수: 단계마다 한 줄 주석
- 비자명한 조건 분기·예외 처리: "왜 이 분기를 두는가"
- 도메인 규칙이 코드에 직접 드러나지 않을 때 (예: SRS 채점 매핑)

## 어떤 경우에 주석을 달지 않는가

- 한두 줄짜리 자명한 함수
- 타입 시그니처/네이밍으로 의도가 다 드러나는 경우
- "이 코드는 X를 한다" 같은 동어반복

## 예시

```python
async def issue_tokens(user: User) -> TokenPair:
    # access 토큰은 짧게, 본문에 담아 응답
    access = encode_access(user.id)
    # refresh 토큰은 DB 에 해시 저장 + 쿠키로 전달 (재사용 감지를 위한 family 추적)
    refresh, jti = encode_refresh(user.id, family_id=new_family_id())
    await refresh_token_repo.save(user.id, jti, sha256(refresh))
    return TokenPair(access=access, refresh=refresh)
```

```typescript
// 401 응답이 오면 단일 refresh Promise 로 동시 요청을 큐잉 — race condition 방지
async function fetchWithAuth(url: string, init?: RequestInit): Promise<Response> {
  const res = await rawFetch(url, attachAuth(init));
  if (res.status !== 401) return res;
  await sharedRefreshPromise();
  return rawFetch(url, attachAuth(init));
}
```

## 안티 패턴

```python
# bad — 동어 반복
def add(a: int, b: int) -> int:
    # a 와 b 를 더한다
    return a + b

# bad — 줄마다 설명
def f():
    x = 1  # x 를 1로 초기화
    y = 2  # y 를 2로 초기화
    return x + y  # x 와 y 를 더해 반환
```
