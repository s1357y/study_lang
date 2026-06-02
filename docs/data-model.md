# Data Model

스키마의 단일 출처는 `backend/app/models/` (SQLAlchemy) + `backend/alembic/versions/`. 이 문서는 모델의 **의도**와 **불변식**을 설명한다.

## ER 개요

```
User ─┬─< RefreshToken (1:N)   ← 인증/회전 추적
      ├─< UserProfile (1:1)
      ├─< MotivationState (1:1)
      ├─< StudySession (1:N)
      ├─< ReviewRecord (1:N) ─── ContentItem
      └─< AttemptLog (1:N) ───── Problem ───── ContentItem
```

## 모델 상세

### User
- `id` (uuid), `email` (unique), `password_hash` (argon2id), `email_verified_at` (nullable)
- `target_language` (string, default `"ja"`)
- `level` (enum: `BEGINNER` | `ELEMENTARY` | `INTERMEDIATE` | `UPPER_INTERMEDIATE` | `ADVANCED`)
- `created_at`, `updated_at`

### RefreshToken
- `id` (uuid, == JWT 의 `jti`)
- `user_id` (FK)
- `token_hash` (sha256 hex)
- `family_id` (uuid)
- `parent_id` (uuid, nullable) — 이전 토큰의 id
- `issued_at`, `expires_at`
- `revoked_at` (nullable), `revoked_reason` (string, nullable: `"rotated"` | `"logout"` | `"reuse_detected"` | `"manual"`)
- index: `(user_id, family_id, revoked_at)`

### UserProfile
- `user_id` (FK, unique)
- `tag_stats` (JSONB) — 약점 누적
  ```json
  {
    "te_form": { "seen": 40, "wrong": 18, "last_wrong_at": "..." }
  }
  ```
- `preferred_topics` (string[])
- `updated_at`

### MotivationState
- `user_id` (FK, unique)
- `streak_days` (int), `last_streak_date` (date)
- `xp` (int), `level` (int — xp 곡선 derived)
- `weekly_goal_minutes` (int, default 60), `weekly_progress_minutes` (int), `weekly_period_start` (date)
- `badges` (string[])

### ContentItem
- `id` (uuid)
- `language` (string)
- `level` (enum, 동일 User.level)
- `kind` (enum: `WORD` | `PHRASE` | `SENTENCE` | `GRAMMAR_NOTE`)
- `tags` (string[]) — 정규화된 태그 키
- `topic` (string, nullable)
- `payload` (JSONB) — `kind` 에 따른 구조:
  - WORD: `{ jp, kana, romaji, meaning_ko, pos, example_jp, example_ko }`
  - SENTENCE: `{ jp, kana_breakdown, meaning_ko, notes }`
  - GRAMMAR_NOTE: `{ pattern, explanation_ko, examples: [...] }`
- `source` (enum: `LLM` | `SEED` | `MANUAL`)
- `quality_score` (float 0.0~1.0)
- `generated_at`, `created_at`

**불변식**: `payload` 구조는 `kind` 에 의해 강제. Pydantic 스키마가 검증.

### Problem
- `id` (uuid), `content_item_id` (FK)
- `type` (enum: `MCQ_MEANING` | `MCQ_READING` | `FILL_BLANK` | `TRANSLATION_KO_TO_JP` | `TRANSLATION_JP_TO_KO` | `LISTENING`)
- `prompt`, `answer`, `distractors` (string[])
- `tags` (string[]) — content_item.tags 상속 + 문제 유형 태그
- `meta` (JSONB)
- `created_at`

### StudySession
- `id` (uuid), `user_id` (FK)
- `date` (date — 사용자 timezone 기준)
- `planned_problem_ids` (string[]), `completed_problem_ids` (string[])
- `started_at`, `finished_at` (nullable)

### ReviewRecord (FSRS)
- `id` (uuid), `user_id` (FK), `content_item_id` (FK)
- `stability`, `difficulty` (float)
- `reps`, `lapses` (int)
- `state` (enum: `NEW` | `LEARNING` | `REVIEW` | `RELEARNING`)
- `last_reviewed_at` (timestamptz, nullable), `next_due_at` (timestamptz)
- `created_at`
- **unique**: `(user_id, content_item_id)`

### AttemptLog
- `id` (uuid), `user_id` (FK), `problem_id` (FK)
- `content_item_id` (FK, denormalized for 빠른 조회)
- `correct` (bool), `response_time_ms` (int)
- `mistake_tags` (string[])
- `created_at`

## 인덱스 (최소)

- `ReviewRecord(user_id, next_due_at)` — 일일 복습 조회
- `ContentItem(language, level, tags)` GIN — 풀 조회
- `AttemptLog(user_id, created_at)` — 통계
- `StudySession(user_id, date)` unique — 하루 1세션
- `RefreshToken(user_id, family_id, revoked_at)` — refresh 회전/재사용 감지

## 마이그레이션 절차

1. `backend/app/models/<entity>.py` 에 SQLAlchemy 모델 추가/수정
2. `backend/app/models/__init__.py` 에서 모델 import (Base.metadata 등록 보장)
3. `cd backend && uv run alembic revision --autogenerate -m "<descriptive>"`
4. 생성된 마이그레이션 스크립트 검토 (autogenerate 가 누락하는 변경 보충)
5. `uv run alembic upgrade head`
6. 변경된 컬럼/테이블을 사용하는 서비스/스키마 함께 갱신

자세한 가이드는 [`backend/rules/schema-migrations.md`](../backend/rules/schema-migrations.md).
