"use client";

// 레벨업 시험 결과 화면 — 합격/불합격 + 다음 레벨 안내.

import Link from "next/link";

import type { LevelUpResult } from "@/lib/api/backend";

const LEVEL_LABEL: Record<string, string> = {
  BEGINNER: "N5",
  ELEMENTARY: "N4",
  INTERMEDIATE: "N3",
  ADVANCED: "N2",
};

export function LevelUpResultView({ result }: { result: LevelUpResult }) {
  const pct = Math.round(result.score * 100);

  return (
    <div className="rounded-2xl border border-neutral-200 bg-white p-8 text-center">
      <p className="text-5xl">{result.passed ? "🎉" : "📚"}</p>
      <h2 className="mt-4 text-2xl font-bold">
        {result.passed ? "합격!" : "불합격"}
      </h2>
      <p className="mt-2 text-neutral-600">
        {result.correct}/{result.total}문제 정답 ({pct}%)
      </p>
      <p className="mt-4 text-sm text-neutral-700 leading-relaxed">
        {result.message}
      </p>
      {result.passed && (
        <div className="mt-4 rounded-xl bg-green-50 px-4 py-3">
          <p className="text-sm font-semibold text-green-800">
            {LEVEL_LABEL[result.from_level] ?? result.from_level} →{" "}
            {LEVEL_LABEL[result.to_level] ?? result.to_level} 승급!
          </p>
        </div>
      )}
      <Link
        href="/dashboard"
        className="mt-6 inline-block rounded-xl bg-neutral-900 px-6 py-3 text-sm font-semibold text-white hover:bg-neutral-700"
      >
        대시보드로
      </Link>
    </div>
  );
}
