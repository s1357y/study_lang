# Backend Structure — FastAPI

## 디렉토리

```
backend/
├── CLAUDE.md             # 작업 규칙 (인덱스)
├── STRUCTURE.md          # ← 이 파일
├── rules/                # CLAUDE.md 에서 링크되는 세부 규칙
│   ├── layer-boundaries.md
│   ├── auth-flow.md
│   ├── llm-calls.md
│   └── schema-migrations.md
├── README.md
├── pyproject.toml
├── alembic.ini
├── alembic/              # ★ 스키마 단일 출처 (autogenerate)
│   ├── env.py            # target_metadata = Base.metadata
│   └── versions/
└── app/
    ├── main.py           # FastAPI 진입점
    ├── core/             # config/security/logging (도메인 비종속)
    │   ├── config.py
    │   ├── security.py   # 비밀번호 해싱(argon2) + JWT 인코딩/검증
    │   └── logging.py
    ├── api/
    │   └── v1/
    │       ├── routes/
    │       │   ├── auth.py          # /auth/register, /login, /refresh, /logout, /me  (Phase 2)
    │       │   ├── health.py
    │       │   ├── sessions.py      # /sessions/today  (Phase 4)
    │       │   ├── problems.py      # (Phase 5)
    │       │   ├── attempts.py      # (Phase 4)
    │       │   └── user_stats.py    # (Phase 6)
    │       └── deps.py              # current_user_claims 등
    ├── domain/           # 순수 비즈니스 모델 (Pydantic)
    ├── services/         # 비즈니스 오케스트레이션
    │   ├── auth_service.py        # (Phase 2)
    │   ├── srs_service.py         # (Phase 4)
    │   ├── weakness_service.py    # (Phase 4)
    │   ├── content_service.py     # (Phase 3)
    │   └── generation_service.py  # (Phase 3)
    ├── llm/              # LLM 추상화
    │   ├── client.py     # Ollama 호출 + list_models()
    │   ├── prompts/      # Jinja 템플릿
    │   ├── schemas.py    # LLM 응답 Pydantic
    │   └── validators.py # 일본어 정합성 검증
    ├── repositories/     # DB CRUD (SQLAlchemy)
    │   ├── user_repo.py
    │   ├── refresh_token_repo.py
    │   ├── content_repo.py
    │   ├── review_repo.py
    │   └── attempt_repo.py
    ├── models/           # ★ SQLAlchemy ORM — 스키마 단일 출처
    │   ├── base.py       # DeclarativeBase
    │   ├── user.py
    │   ├── refresh_token.py
    │   └── ... (도메인 모델들)
    ├── workers/          # 백그라운드 작업 (APScheduler)
    │   └── content_pregen.py
    └── utils/
```

## 계층 책임 (위에서 아래)

```
api/routes  →  services  →  repositories  →  models (SQLAlchemy)
                  │
                  ↓
                 llm/
```

자세한 정의는 [`rules/layer-boundaries.md`](./rules/layer-boundaries.md).

## 인증

- 토큰 흐름은 [`rules/auth-flow.md`](./rules/auth-flow.md) (도메인 정책은 [`/docs/auth-flow.md`](../docs/auth-flow.md))
- 보호 라우트는 `Depends(current_user_claims)` 로 access 클레임 주입.
- 사용자 객체가 필요한 경우 별도 의존성으로 DB 조회.

## 스키마 단일 출처

- 모델은 `app/models/`, 마이그레이션은 `alembic/versions/`.
- 절차는 [`rules/schema-migrations.md`](./rules/schema-migrations.md).

## LLM 호출

- 진입점은 `app/llm/client.py` 만. 프롬프트는 `app/llm/prompts/*.j2`.
- 자세히 [`rules/llm-calls.md`](./rules/llm-calls.md).

## 설정

- `core/config.py` 의 `Settings` (pydantic-settings) 가 환경변수 단일 진입점.
- `os.getenv` 직접 사용 금지.

## 테스트 (Phase 5+)

- pytest + pytest-asyncio
- DB 통합 테스트는 별도 테스트 DB (Docker Compose 의 postgres 위에 db 생성)
- LLM 은 mock — 실제 호출은 별도 e2e 스위트
