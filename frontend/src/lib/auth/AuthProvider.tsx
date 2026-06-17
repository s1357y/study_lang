"use client";

// 인증 상태 컨텍스트 — 컴포넌트 트리에서 useAuth 로 접근.
// 부팅 시 /auth/refresh 한 번 호출해 access 토큰을 복구한다.

import { useRouter } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";

import {
  authBootstrap,
  authLogin,
  authLogout,
  authRegister,
  type UserPublic,
} from "@/lib/api/backend";
import {
  setAccessToken,
  setUnauthorizedHandler,
} from "@/lib/auth/tokenStore";

type AuthState =
  | { status: "loading" }
  | { status: "anonymous" }
  | { status: "authenticated"; user: UserPublic };

type AuthContextValue = {
  state: AuthState;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  updateUser: (user: UserPublic) => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [state, setState] = useState<AuthState>({ status: "loading" });

  // refresh 가 실패해 인증이 끊긴 경우 사인인 페이지로 이동
  useEffect(() => {
    setUnauthorizedHandler(() => {
      setState({ status: "anonymous" });
      router.replace("/sign-in");
    });
    return () => setUnauthorizedHandler(null);
  }, [router]);

  // 마운트 시 한 번 refresh 시도 — 성공하면 access 복구
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const data = await authBootstrap();
      if (cancelled) return;
      if (data) setState({ status: "authenticated", user: data.user });
      else setState({ status: "anonymous" });
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const data = await authLogin(email, password);
    setState({ status: "authenticated", user: data.user });
  }, []);

  const register = useCallback(async (email: string, password: string) => {
    const data = await authRegister(email, password);
    setState({ status: "authenticated", user: data.user });
  }, []);

  const logout = useCallback(async () => {
    // authLogout 내부 finally 에서 setAccessToken(null) 을 처리하므로 여기선 상태만 전환
    await authLogout();
    setState({ status: "anonymous" });
    router.replace("/sign-in");
  }, [router]);

  const updateUser = useCallback((user: UserPublic) => {
    setState({ status: "authenticated", user });
  }, []);

  return (
    <AuthContext.Provider value={{ state, login, register, logout, updateUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
