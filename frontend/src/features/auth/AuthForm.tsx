"use client";

// 사인인/사인업 공용 폼 — 동작은 props.onSubmit 으로 주입받아 두 페이지에서 재사용.

import { useState } from "react";

import { ApiError } from "@/lib/api/backend";

type Props = {
  title: string;
  submitLabel: string;
  onSubmit: (email: string, password: string) => Promise<void>;
  footer?: React.ReactNode;
};

export function AuthForm({ title, submitLabel, onSubmit, footer }: Props) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await onSubmit(email, password);
    } catch (err) {
      if (err instanceof ApiError) {
        // 런타임 타입 가드 — as 단언 없이 실제 구조를 확인한다
        const raw = err.detail;
        const message =
          raw !== null &&
          typeof raw === "object" &&
          "detail" in raw &&
          typeof (raw as Record<string, unknown>).detail === "string"
            ? (raw as { detail: string }).detail
            : null;
        setError(message ?? "요청에 실패했습니다.");
      } else {
        setError("네트워크 오류가 발생했습니다.");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-sm flex-col justify-center px-6 py-16">
      <h1 className="text-2xl font-bold">{title}</h1>

      <form onSubmit={handleSubmit} className="mt-6 flex flex-col gap-4">
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-neutral-700">이메일</span>
          <input
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="rounded-lg border border-neutral-300 px-3 py-2"
          />
        </label>

        <label className="flex flex-col gap-1 text-sm">
          <span className="text-neutral-700">비밀번호</span>
          <input
            type="password"
            required
            minLength={8}
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="rounded-lg border border-neutral-300 px-3 py-2"
          />
        </label>

        {error && (
          <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={busy}
          className="rounded-lg bg-neutral-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
        >
          {busy ? "처리 중…" : submitLabel}
        </button>
      </form>

      {footer && <div className="mt-6 text-sm text-neutral-600">{footer}</div>}
    </main>
  );
}
