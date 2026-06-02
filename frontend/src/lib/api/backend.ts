// 백엔드 호출의 단일 진입점.
//
// 책임:
// 1) Authorization 헤더 자동 첨부
// 2) credentials: "include" — refresh 쿠키 전송
// 3) 401 응답 시 자동으로 /auth/refresh 호출 후 재시도
// 4) 동시 401 들이 단일 refresh Promise 를 공유 (race 방지)
//
// 컴포넌트/feature 는 이 파일의 함수만 사용한다. raw fetch 금지.

import {
  getAccessToken,
  notifyUnauthorized,
  setAccessToken,
} from "@/lib/auth/tokenStore";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

// ============================================================================
// 타입
// ============================================================================

export type UserPublic = {
  id: string;
  email: string;
  target_language: string;
  level: string;
};

export type TokenResponse = {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
  user: UserPublic;
};

export class ApiError extends Error {
  readonly status: number;
  readonly detail: unknown;
  constructor(status: number, detail: unknown, message?: string) {
    super(message ?? `API error ${status}`);
    this.status = status;
    this.detail = detail;
  }
}

// ============================================================================
// 401 리프레시 큐잉
// ============================================================================

// 동시 다발 401 이 발생해도 /auth/refresh 는 단 한 번만 호출되도록 공유 Promise
let inflightRefresh: Promise<boolean> | null = null;

async function performRefresh(): Promise<boolean> {
  // 쿠키가 자동 첨부되도록 credentials: "include"
  try {
    const res = await fetch(`${BACKEND_URL}/api/v1/auth/refresh`, {
      method: "POST",
      credentials: "include",
    });
    if (!res.ok) return false;
    const data = (await res.json()) as TokenResponse;
    setAccessToken(data.access_token);
    return true;
  } catch {
    return false;
  }
}

async function refreshOnce(): Promise<boolean> {
  // 단일 비행 보장 — 후속 호출자는 모두 같은 Promise 를 await
  inflightRefresh ??= performRefresh().finally(() => {
    inflightRefresh = null;
  });
  return inflightRefresh;
}

// ============================================================================
// fetch 래퍼
// ============================================================================

type RequestOptions = {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  // true 면 401 시 refresh 시도하지 않음 — /auth/refresh, /auth/login 등에 사용
  skipAuthRetry?: boolean;
  // true 면 Authorization 헤더를 첨부하지 않음 — register/login 등 공개 엔드포인트용
  skipAuthHeader?: boolean;
  signal?: AbortSignal;
};

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, skipAuthRetry, skipAuthHeader, signal } = opts;

  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (!skipAuthHeader) {
    const token = getAccessToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  const doFetch = () =>
    fetch(`${BACKEND_URL}${path}`, {
      method,
      headers,
      credentials: "include",
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
    });

  let res = await doFetch();

  // access 만료로 401 이 나면 refresh 한 번 시도 후 재호출
  if (res.status === 401 && !skipAuthRetry) {
    const refreshed = await refreshOnce();
    if (refreshed) {
      const token = getAccessToken();
      if (token) headers["Authorization"] = `Bearer ${token}`;
      res = await doFetch();
    } else {
      // refresh 실패 → 인증 상태 비우고 사인인 페이지 이동 신호
      setAccessToken(null);
      notifyUnauthorized();
    }
  }

  if (!res.ok) {
    let detail: unknown = null;
    try {
      detail = await res.json();
    } catch {
      detail = await res.text();
    }
    throw new ApiError(res.status, detail);
  }

  // 204 No Content 는 본문 없음
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

// ============================================================================
// 도메인 함수
// ============================================================================

export async function getBackendHealth(): Promise<unknown> {
  try {
    return await request("/healthz", { skipAuthHeader: true, skipAuthRetry: true });
  } catch (err) {
    return { status: "unreachable", error: String(err) };
  }
}

export async function authRegister(
  email: string,
  password: string,
): Promise<TokenResponse> {
  const data = await request<TokenResponse>("/api/v1/auth/register", {
    method: "POST",
    body: { email, password },
    skipAuthHeader: true,
    skipAuthRetry: true,
  });
  setAccessToken(data.access_token);
  return data;
}

export async function authLogin(
  email: string,
  password: string,
): Promise<TokenResponse> {
  const data = await request<TokenResponse>("/api/v1/auth/login", {
    method: "POST",
    body: { email, password },
    skipAuthHeader: true,
    skipAuthRetry: true,
  });
  setAccessToken(data.access_token);
  return data;
}

// 부팅 시 호출 — refresh 쿠키가 있으면 access 복구
export async function authBootstrap(): Promise<TokenResponse | null> {
  try {
    const data = await request<TokenResponse>("/api/v1/auth/refresh", {
      method: "POST",
      skipAuthHeader: true,
      skipAuthRetry: true,
    });
    setAccessToken(data.access_token);
    return data;
  } catch {
    return null;
  }
}

export async function authLogout(): Promise<void> {
  try {
    await request("/api/v1/auth/logout", {
      method: "POST",
      skipAuthHeader: true,
      skipAuthRetry: true,
    });
  } finally {
    setAccessToken(null);
  }
}

export async function authMe(): Promise<UserPublic> {
  return request<UserPublic>("/api/v1/auth/me");
}

// ============================================================================
// 학습 도메인 타입
// ============================================================================

export type StudyStats = {
  due_today: number;
  new_available: number;
  weak_tags: string[];
};

export type ProblemOut = {
  problem_id: string;
  content_item_id: string;
  // 백엔드 ProblemType 소문자 값과 동일하게 유지
  problem_type: "mcq_meaning" | "mcq_reading" | "fill_blank" | "short_answer" | "translation" | "listening";
  prompt: string;
  answer: string;
  distractors: string[];
  tags: string[];
};

export type StudySession = {
  id: string;
  date: string;
  problems: ProblemOut[];
  completed_count: number;
  total_count: number;
  started_at: string;
};

export type AttemptResult = {
  id: string;
  correct: boolean;
  rating: string | null;
  next_due_at: string;
  created_at: string;
};

export type SubmitAttemptBody = {
  problem_id: string;
  content_item_id: string;
  correct: boolean;
  response_time_ms: number;
};

// ============================================================================
// 학습 도메인 함수
// ============================================================================

export async function fetchStudyStats(): Promise<StudyStats> {
  return request<StudyStats>("/api/v1/study/stats");
}

// POST — 오늘 세션이 있으면 재사용, 없으면 생성
export async function fetchTodaySession(): Promise<StudySession> {
  return request<StudySession>("/api/v1/study/sessions/today", {
    method: "POST",
  });
}

export async function submitAttempt(
  body: SubmitAttemptBody,
): Promise<AttemptResult> {
  return request<AttemptResult>("/api/v1/study/attempts", {
    method: "POST",
    body,
  });
}

// ============================================================================
// 동기부여 도메인 타입
// ============================================================================

export type MotivationState = {
  streak_days: number;
  xp: number;
  level: number;
  weekly_goal_minutes: number;
  weekly_progress_seconds: number;
  weekly_progress_minutes: number;
  weekly_period_start: string | null;
};

// ============================================================================
// 동기부여 도메인 함수
// ============================================================================

export async function fetchMotivation(): Promise<MotivationState> {
  return request<MotivationState>("/api/v1/motivation");
}
