# SRS Algorithm — FSRS

## 채택 알고리즘: FSRS (Free Spaced Repetition Scheduler)

- 라이브러리: [`py-fsrs`](https://github.com/open-spaced-repetition/py-fsrs)
- 이유:
  - SM-2(Anki 기본)보다 더 적은 복습 횟수로 같은 retention을 달성한다는 실증 데이터가 있음.
  - 4지 등급(`Again`/`Hard`/`Good`/`Easy`)을 그대로 사용 가능.
  - `stability`, `difficulty` 변수가 사용자별로 학습되므로 우리 시스템의 사용자 특화 목표와 잘 맞음.

## 채점 매핑

문제 풀이 결과를 FSRS 등급으로 변환하는 규칙:

| 상황 | 등급 |
|-----|-----|
| 오답 | `Again` |
| 정답 + 응답시간 > 평균*1.5 | `Hard` |
| 정답 + 평균 응답시간 범위 | `Good` |
| 정답 + 응답시간 < 평균*0.6 | `Easy` |

응답시간 "평균"의 기준:
- 동일 사용자의 같은 문제 유형 직전 30회 응답시간 중앙값.
- 데이터 부족(<10회)이면 모든 정답을 `Good`으로 처리.

## 상태 전이

```
NEW ──first attempt──▶ LEARNING ──graduation──▶ REVIEW
                                                  │
                          ◀───lapse(Again)────────┤
                          │                       ▼
                        RELEARNING            REVIEW (다음 만기)
```

## 일일 복습 큐 구성

`srs_service.due_today(user)`:
1. `next_due_at <= now()` 조건의 `ReviewRecord` 조회
2. 정렬: `state == LEARNING` 우선, 그 다음 `lapses DESC`, 그 다음 `next_due_at ASC`
3. 상한: 사용자 daily review cap (기본 40, MotivationState/preferences에서 조정 가능)

## 신규 학습 카드 수 결정

신규 카드 수 = `min(daily_new_cap, 20)` 단,
- 오늘 복습이 30개 이상이면 신규는 절반으로 줄임 (인지 부하 보호)
- 스트릭이 끊긴 직후 첫 날은 신규를 줄이고 복습 위주

## 파라미터 조정

`py-fsrs`의 기본 가중치로 시작. 향후 사용자별 데이터가 충분히 쌓이면(>200 ReviewRecord) `optimize()`로 개인화. 글로벌 가중치 변경은 마이그레이션 영향이 있으므로 ADR로 결정.

## 약점 태그와의 관계

FSRS는 **카드 단위 스케줄**만 담당한다. 사용자 약점 태그 집계는 **별도의 `weakness_service`**가 처리하며, LLM 프롬프트 주입과 신규 카드 선택 가중치에만 영향을 준다. 두 시스템을 섞지 않는다.
