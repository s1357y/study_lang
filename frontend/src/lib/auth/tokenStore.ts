// 메모리에만 보관하는 access 토큰 저장소.
// 컴포넌트 트리 밖(fetch 래퍼 등)에서도 접근 가능해야 해서 모듈 변수로 둔다.
// localStorage 사용 금지 — XSS 방어.

let _accessToken: string | null = null;

// 인증 상태가 무너졌을 때 (refresh 실패 등) 호출되는 콜백 — AuthProvider 가 등록한다
let _onUnauthorized: (() => void) | null = null;

export function setAccessToken(token: string | null): void {
  _accessToken = token;
}

export function getAccessToken(): string | null {
  return _accessToken;
}

export function setUnauthorizedHandler(handler: (() => void) | null): void {
  _onUnauthorized = handler;
}

export function notifyUnauthorized(): void {
  // 핸들러가 등록되어 있으면 호출 — 보통 사인인 페이지로 리다이렉트
  _onUnauthorized?.();
}
