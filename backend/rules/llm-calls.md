# LLM 호출 규약

## 단일 진입점

- 모든 Ollama 호출은 `app/llm/client.py` 의 함수만 사용:
  - `generate_json(prompt, model?, temperature?, timeout?)` — 콘텐츠/문제 생성
  - `list_models(timeout?)` — 진단/헬스 체크
- 외부에서 `httpx` 로 `http://...:11434` 를 직접 부르지 않는다.

## 프롬프트

- 인라인 문자열 금지. 반드시 `app/llm/prompts/<purpose>.j2` (Jinja2) 템플릿.
- 템플릿은 변수 주입 + 출력 JSON 스키마 명시.
- 같은 목적의 프롬프트는 한 파일로 모은다.

## 응답 검증

- LLM 응답 JSON 은 Pydantic 모델로 파싱 (`llm/schemas.py`).
- 비즈니스 저장 전 `llm/validators.py` 통과 (일본어 정합성, 중복 등).
- 검증 실패 시 폐기 — 사용자에게 노출 금지.

## 동시성

- Ollama 단일 인스턴스 전제 — 워커 작업은 동시 1개로 제한.
- 사용자 요청 경로의 LLM 호출이 있으면 워커가 양보하도록 설계.
- 사용자 응답 경로에서 호출 시 최대 대기 10초 후 폴링/플레이스홀더 전략.

## 모델 / 파라미터

- 모델 기본값: `settings.ollama_model` (호출측에서 오버라이드 가능).
- 온도/타임아웃은 호출 함수가 명시. 매직 넘버 금지.

## 금지

- services 에서 raw `httpx` 호출
- 프롬프트를 코드 안에 문자열로 (반드시 템플릿 파일)
- 검증되지 않은 LLM 출력을 DB에 직접 저장
