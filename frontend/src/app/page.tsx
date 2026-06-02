"use client";

// 랜딩 페이지 — 인증 상태에 따라 진입 경로를 다르게 안내.

import Link from "next/link";

import { useAuth } from "@/lib/auth/AuthProvider";

export default function HomePage() {
  const { state } = useAuth();

  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col gap-8 px-6 py-16">
      <header>
        <h1 className="text-4xl font-bold">LingoLab</h1>
        <p className="mt-2 text-neutral-600">
          AI 기반 개인화 일본어 학습 플랫폼
        </p>
      </header>

      <section className="rounded-xl border border-neutral-200 bg-white p-6">
        {state.status === "loading" && (
          <p className="text-sm text-neutral-500">인증 상태 확인 중…</p>
        )}
        {state.status === "anonymous" && (
          <div className="flex flex-col gap-3">
            <p className="text-sm text-neutral-700">시작하려면 로그인하세요.</p>
            <div className="flex gap-2">
              <Link
                href="/sign-in"
                className="rounded-lg bg-neutral-900 px-4 py-2 text-sm font-medium text-white"
              >
                로그인
              </Link>
              <Link
                href="/sign-up"
                className="rounded-lg border border-neutral-300 px-4 py-2 text-sm font-medium"
              >
                회원가입
              </Link>
            </div>
          </div>
        )}
        {state.status === "authenticated" && (
          <div className="flex flex-col gap-3">
            <p className="text-sm text-neutral-700">
              안녕하세요, <strong>{state.user.email}</strong>.
            </p>
            <Link
              href="/dashboard"
              className="self-start rounded-lg bg-neutral-900 px-4 py-2 text-sm font-medium text-white"
            >
              학습 대시보드로 이동
            </Link>
          </div>
        )}
      </section>
    </main>
  );
}
