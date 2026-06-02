# 계층 경계 규칙

## 호출 방향 (위에서 아래로만)

```
api/routes  →  services  →  repositories  →  models (SQLAlchemy)
                  │
                  ↓
                 llm/
```

## 계층별 책임

### `api/routes/`
- HTTP 요청/응답, 인증 가드(`Depends(current_user_claims)`), 입력 검증 (Pydantic).
- **비즈니스 로직 없음**. services 만 호출.
- 응답 직렬화는 Pydantic 모델.

### `services/`
- 여러 repo / llm 을 묶는 오케스트레이션.
- 트랜잭션 경계.
- routes 의 요청 모델 → 도메인 작업 → routes 응답 모델 변환.

### `repositories/`
- DB CRUD 만. SQLAlchemy 쿼리는 여기에만.
- 도메인 객체 (Pydantic) 또는 ORM 객체 둘 다 반환 가능. 호출측이 결정.

### `domain/`
- Pydantic 모델 (순수). 어디서든 import 가능.
- DB 와 무관한 비즈니스 객체.

### `models/`
- SQLAlchemy ORM. repositories 외 import 금지.
- Base.metadata 의 단일 출처.

### `llm/`
- Ollama 호출 + 검증 + 프롬프트 템플릿.
- services 에서만 호출.

## 위반 사례

```python
# bad — route 가 repository 직접 호출
@router.get("/today")
async def get_today(current = Depends(current_user_claims)):
    return await review_repo.due_today(current.sub)  # ✗

# good — service 경유
@router.get("/today")
async def get_today(current = Depends(current_user_claims)):
    return await session_service.build_today(current.sub)  # ✓
```

```python
# bad — service 가 httpx 직접
async def generate_card(...):
    resp = await httpx.post(f"{settings.ollama_host}/api/generate", ...)  # ✗

# good — llm/client.py 경유
async def generate_card(...):
    return await llm_client.generate_json(prompt)  # ✓
```
