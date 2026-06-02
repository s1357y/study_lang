# 스키마 변경 절차

## 단일 출처

- **DB 스키마는 `backend/app/models/` (SQLAlchemy) + `backend/alembic/versions/` 만이 정답.**
- 프론트엔드에는 ORM 의존성이 없다 (Prisma 등 사용 금지).

## 변경 절차

1. `app/models/<entity>.py` 에 SQLAlchemy 모델 추가/수정
2. `app/models/__init__.py` 에서 모델 import (Base.metadata 등록 보장)
3. 의존하는 도메인/서비스 코드 수정
4. 마이그레이션 생성:
   ```bash
   uv run alembic revision --autogenerate -m "<descriptive_name>"
   ```
5. 생성된 마이그레이션 스크립트 검토:
   - autogenerate 가 누락하는 변경(예: 데이터 마이그레이션, 일부 인덱스, ENUM 변경) 직접 보충
   - 컬럼 삭제 / 타입 변경 등 위험한 변경은 다단계 마이그레이션 고려
6. 적용:
   ```bash
   uv run alembic upgrade head
   ```
7. 롤백 시험 (선택):
   ```bash
   uv run alembic downgrade -1
   uv run alembic upgrade head
   ```

## 명명 규칙

- 마이그레이션 메시지: 영어 동사 + 명사 (예: `add_refresh_token`, `widen_content_payload_index`)
- 테이블명: 단수형 snake_case (`user`, `content_item`, `refresh_token`)
- 컬럼명: snake_case
- 인덱스명: Alembic 기본값을 신뢰

## 새 모델 체크리스트

- [ ] `id` 컬럼 (대부분 UUID)
- [ ] `created_at` / `updated_at` (필요 시)
- [ ] 외래키에 `ondelete` 명시 (예: `CASCADE`)
- [ ] 자주 조회되는 컬럼에 인덱스
- [ ] JSONB 컬럼은 검증 가능한 Pydantic 스키마와 짝지어 사용

## 금지

- SQLAlchemy 모델 없이 raw SQL 마이그레이션 (인덱스/뷰만 예외)
- 프로덕션 DB 에 수동 ALTER (반드시 마이그레이션 경유)
- 한 번에 여러 무관한 변경을 한 마이그레이션에 묶기
