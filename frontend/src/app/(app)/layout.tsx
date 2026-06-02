"use client";

// 보호 영역 레이아웃 — MVP 는 클라이언트 가드.
// 부팅 중에는 로딩, 비인증이면 사인인으로 리다이렉트.

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { useAuth } from "@/lib/auth/AuthProvider";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { state, logout } = useAuth();

  useEffect(() => {
    if (state.status === "anonymous") router.replace("/sign-in");
  }, [state.status, router]);

  if (state.status === "loading") {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-neutral-500">
        인증 상태 확인 중…
      </div>
    );
  }

  if (state.status !== "authenticated") {
    // 리다이렉트가 잡힐 때까지 잠시 비워둠
    return null;
  }

  return (
    <div className="min-h-screen">
      <header className="border-b border-neutral-200 bg-white">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-6 py-3">
          <span className="text-sm font-semibold">LingoLab</span>
          <div className="flex items-center gap-3 text-sm">
            <span className="text-neutral-600">{state.user.email}</span>
            <button
              onClick={() => void logout()}
              className="rounded-lg border border-neutral-300 px-3 py-1 text-xs"
            >
              로그아웃
            </button>
          </div>
        </div>
      </header>
      <div className="mx-auto max-w-4xl px-6 py-8">{children}</div>
    </div>
  );
}
