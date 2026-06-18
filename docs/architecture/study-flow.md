# 학습 흐름 아키텍처

## 전체 흐름 요약

```
[대시보드]
  └─ 학습 시작 → POST /study/sessions/today
        │
        ├─ 기존 세션 재사용 (당일 이미 생성된 경우)
        └─ 신규 세션 생성
              ├─ SRS 복습 큐 조회 (due_today)
              └─ 신규 슬롯 채우기 (get_new_content_items)

[학습 중]
  └─ 문제 풀기 → POST /study/attempts
        ├─ AttemptLog 기록
        ├─ ReviewRecord SRS 갱신 (py-fsrs)
        ├─ MotivationState XP 적립
        └─ StudySession.completed_problem_ids 추가

[완료 후]
  ├─ 더 공부하기 → POST /study/sessions/today/extend
  │     ├─ get_new_content_items() 로 미학습 아이템 조회
  │     └─ 풀 소진 시 generation_service.generate_vocabulary() 로 LLM 생성
  └─ 레벨업 배너 (응시 자격 충족 시)
        └─ GET /level-up/eligibility → eligible=true
              └─ /level-up 페이지로 이동
```

## 두 가지 레벨 필드

| 필드 | 위치 | 의미 | 변경 조건 |
|---|---|---|---|
| `User.level` | `user` 테이블 | JLPT 레벨 (BEGINNER/ELEMENTARY/INTERMEDIATE/ADVANCED) | 배치 시험 or 레벨업 시험 통과 시만 |
| `MotivationState.level` | `motivation_state` 테이블 | 게임화 레벨 (1, 2, 3…) | XP 적립마다 자동 계산 (`floor(sqrt(xp/100)) + 1`) |

**혼동 주의**: `User.level`은 학습 콘텐츠 레벨 필터에 사용, `MotivationState.level`은 UI 표시용.

## 레벨 승급 경로

```
BEGINNER (N5) → ELEMENTARY (N4) → INTERMEDIATE (N3) → ADVANCED (N2)
```

- 배치 시험: 첫 로그인 후 1회, 점수 기반 자동 배정
- 레벨업 시험: 현재 레벨 30개+ 학습 후 응시 가능, 70% 합격, 7일 쿨다운

## 핵심 불변식

1. **콘텐츠 풀 분리**: vocabulary / grammar 두 종류. `ContentItem.kind` 로 구분.
2. **문제 선저장 유형**: MCQ_GRAMMAR·MCQ_CONTEXT·MCQ_SYNONYM은 생성 시 `Problem.distractors` JSONB에 선저장. 세션 빌드 시 풀 조회 불필요.
3. **동적 유형**: MCQ_MEANING·MCQ_READING·FILL_BLANK는 같은 레벨·kind 풀에서 동적 추출. FILL_BLANK는 `payload["word"]` 기준으로 오답 선택지 구성 — DB의 `distractors` 컬럼은 비어 있어도 무방.
4. **ReviewRecord 선생성**: 세션 빌드 시 신규 ContentItem마다 `get_or_create()` 호출 → `get_new_content_items()`가 이 아이템을 다시 반환하지 않음.
5. **completed_problem_ids ARRAY**: list 재할당으로 dirty flag 트리거 (SQLAlchemy mutable 한계).

## 수정 시 함께 변경해야 할 파일

| 변경 대상 | 함께 확인할 파일 |
|---|---|
| `study_service.py` | `study.py` 라우트, `useStudySession.ts`, `useSubmitAttempt.ts` |
| `srs_service.py` | `study_service.py` |
| `study_session_repo.py` | `study_service.py` |
| `level_up_service.py` | `routes/level_up.py`, `LevelUpExamView.tsx`, `useLevelUpEligibility.ts` |
| `placement_service.py` | `routes/placement.py`, `PlacementView.tsx` |
| `generation_service.py` | `study_service.extend_today_session()` |
| `content_repo.get_problems_for_placement()` | `placement_service.py`, `level_up_service.py` |
