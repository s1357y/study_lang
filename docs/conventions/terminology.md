# 도메인 용어 사전

코드의 모델명·엔드포인트명·UI 텍스트 모두 이 용어로 통일한다.

| 한국어 | 영문 (식별자) | 의미 |
|-------|--------------|-----|
| 콘텐츠 항목 | `ContentItem` | 학습 단위 (단어/예문/문법 설명) |
| 문제 | `Problem` | ContentItem 에서 파생된 문제 |
| 풀이 시도 | `Attempt` (`AttemptLog`) | 한 번의 문제 풀이 |
| 복습 기록 | `ReviewRecord` | SRS 스케줄 항목 (콘텐츠당 1개) |
| 약점 태그 | `Tag` | 카테고리 분류 키 (예: `te_form`, `transitive_pair`) |
| 일일 세션 | `StudySession` | 사용자의 하루 학습 묶음 (신규 + 복습) |
| 사용자 프로필 | `UserProfile` | 약점 누적 + 선호 주제 |
| 동기 상태 | `MotivationState` | 스트릭 / XP / 주간 목표 진행도 |
| 접근 토큰 | access token | 짧은 수명 JWT, 응답 본문 전달 |
| 갱신 토큰 | refresh token | 긴 수명 JWT, HttpOnly 쿠키 전달 |
| 토큰 패밀리 | refresh family | 회전 추적을 위한 그룹 (`family_id`) |
