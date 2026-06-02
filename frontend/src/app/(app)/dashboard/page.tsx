"use client";

// 대시보드 — 오늘 학습 현황(복습·신규·약점태그)과 학습 시작 진입점.

import Link from "next/link";

import { MotivationPanel } from "@/features/motivation/components/MotivationPanel";
import { useStudyStats } from "@/features/study/hooks/useStudyStats";

function StatBadge({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex flex-col items-center gap-1 rounded-xl bg-neutral-50 px-6 py-4">
      <span className="text-3xl font-bold tabular-nums">{value}</span>
      <span className="text-xs text-neutral-500">{label}</span>
    </div>
  );
}

export default function DashboardPage() {
  const { data: stats, isLoading, error } = useStudyStats();

  const hasItems =
    stats !== undefined &&
    (stats.due_today > 0 || stats.new_available > 0);

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-bold">대시보드</h1>

      {/* 오늘의 학습 현황 */}
      <section className="rounded-2xl border border-neutral-200 bg-white p-6">
        <h2 className="text-sm font-semibold text-neutral-700">오늘의 학습</h2>

        {isLoading && (
          <p className="mt-3 text-sm text-neutral-400">로딩 중…</p>
        )}

        {error && (
          <p className="mt-3 text-sm text-red-500">
            통계를 불러오지 못했습니다.
          </p>
        )}

        {stats && (
          <>
            <div className="mt-4 flex gap-3">
              <StatBadge label="복습" value={stats.due_today} />
              <StatBadge label="신규" value={stats.new_available} />
            </div>

            {hasItems ? (
              <Link
                href="/study"
                className="mt-5 inline-block rounded-xl bg-neutral-900 px-5 py-2.5 text-sm font-semibold text-white hover:bg-neutral-700"
              >
                학습 시작 →
              </Link>
            ) : (
              <p className="mt-4 text-sm text-neutral-500">
                오늘 학습할 항목이 없습니다. 내일 다시 확인하세요.
              </p>
            )}
          </>
        )}
      </section>

      {/* 동기부여 패널 */}
      <MotivationPanel />

      {/* 약점 태그 */}
      {stats && stats.weak_tags.length > 0 && (
        <section className="rounded-2xl border border-neutral-200 bg-white p-6">
          <h2 className="text-sm font-semibold text-neutral-700">약점 태그</h2>
          <div className="mt-3 flex flex-wrap gap-2">
            {stats.weak_tags.map((tag) => (
              <span
                key={tag}
                className="rounded-full bg-orange-50 px-3 py-1 text-xs font-medium text-orange-700"
              >
                {tag}
              </span>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
