# LLM Strategy

## 목표

1. **데이터 누적 우선**: 콘텐츠 풀에서 먼저 찾고, 부족할 때만 LLM 호출
2. **구조화 출력**: LLM은 항상 JSON 스키마에 맞는 결과를 내야 함
3. **품질 게이트**: 검증을 통과한 콘텐츠만 사용자에게 노출
4. **개인화**: 사용자 약점 태그 + 관심 주제를 프롬프트에 주입

## 생성 vs 재사용 결정 로직

`content_service.fetch_new(user, level, focus_tags, count)` 호출 시:

```
1) DB에서 다음 조건의 ContentItem 조회:
   - language == user.target_language
   - level == user.level (또는 인접 레벨 1개)
   - tags ∩ focus_tags ≠ ∅
   - user의 ReviewRecord에 없는 것 (= 아직 안 본 것)
   - quality_score >= 0.6
2) 결과가 count 이상이면 그대로 반환
3) 부족하면:
   a) 백그라운드 생성 작업이 이미 큐에 있는지 확인
   b) 없으면 generation_service.generate_async(level, focus_tags, n=count*2)
   c) 현재 요청은 가능한 만큼만 반환 + 응답에 "더 곧 생성됨" 플래그
```

## 사전 생성 (Pregeneration)

`workers/content_pregen.py`가 주기적으로:

1. (레벨 × 태그) 매트릭스의 풀 크기를 집계
2. 임계치(기본 50개) 미만인 셀에 대해 LLM 생성 작업 큐잉
3. 인기 태그(최근 7일 사용자들의 약점 빈도 상위)를 우선

이 워커는 사용자 요청과 독립적으로 돌아간다.

## 프롬프트 템플릿 구조

`backend/app/llm/prompts/word_with_example.j2` 같은 Jinja 템플릿. 핵심 변수:

```jinja
당신은 일본어 교사입니다. 다음 조건에 맞는 학습 카드를 JSON 배열로 생성하세요.

레벨: {{ level }}
포커스 태그: {{ focus_tags | join(", ") }}
주제: {{ topic or "자유" }}
개수: {{ count }}

각 카드는 다음 JSON 스키마를 따라야 합니다:
{{ schema_json }}

규칙:
- 일본어는 정확한 가나 표기 포함
- 한국어 의미는 자연스러운 번역
- 예문은 {{ level }}에 맞는 문법만 사용
```

## 출력 검증 (`validators.py`)

각 LLM 응답에 대해:

1. **JSON 파싱 성공** — 실패 시 1회 재시도, 그래도 실패면 폐기
2. **Pydantic 스키마 매칭** — 누락 필드 폐기
3. **일본어 형식 검증**:
   - `jp` 필드에 가나/한자 외 문자 비율 < 5%
   - `kana` 필드는 가나만 포함
   - `romaji`는 ASCII 영문 + 하이픈/공백만
4. **중복 검사** — 동일 `jp`가 같은 레벨 풀에 이미 있으면 폐기 (정확 일치)
5. **품질 점수**:
   - 모든 검증 통과 = 0.8 시작
   - 사용자 실제 풀이에서 정답률에 따라 시간이 흐르며 ±0.2 조정

## 모델 선택

- Phase 0 sanity check에서 다음을 비교:
  - `qwen2.5:7b-instruct` (다국어 강세)
  - `gemma2:9b` (구글, 일본어 데이터 풍부)
  - 가능하면 `qwen2.5:14b-instruct` (성능 여유 시)
- 비교 기준: (a) JSON 스키마 준수율 (b) 일본어 문법 정확도 (c) 응답 지연시간

선택 결과는 `docs/adr/0001-llm-model-selection.md`로 기록.

## 비용/리소스 관리

- 모든 호출은 비동기. 사용자 응답 경로에 LLM이 들어가는 경우 최대 대기 시간 10s 후 폴링으로 전환.
- 사전 생성 작업은 동시 1개만 실행 (Ollama 단일 인스턴스 가정).
- 생성 실패율이 5%를 넘으면 알람 (logs로 기록, 향후 메트릭으로 격상).
