"use client";

// 대시보드 — 오늘 학습 현황(복습·신규·약점태그)과 학습 시작 진입점.

import Link from "next/link";

import { useLevelUpEligibility } from "@/features/level-up/hooks/useLevelUpEligibility";
import { MotivationPanel } from "@/features/motivation/components/MotivationPanel";
import { useStudyStats } from "@/features/study/hooks/useStudyStats";
import { useAuth } from "@/lib/auth/AuthProvider";

const LEVEL_LABEL: Record<string, string> = {
  BEGINNER: "N5",
  ELEMENTARY: "N4",
  INTERMEDIATE: "N3",
  ADVANCED: "N2",
};

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
  const { state } = useAuth();
  const { data: eligibility } = useLevelUpEligibility();

  const user = state.status === "authenticated" ? state.user : null;
  const hasItems =
    stats !== undefined &&
    (stats.due_today > 0 || stats.new_available > 0);

  // 오늘 날짜 UTC 기준
  const todayDate = new Date().toISOString().slice(0, 10);

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-bold">대시보드</h1>

      {/* 레벨업 시험 배너 — 응시 자격 있을 때 표시 */}
      {eligibility?.eligible && eligibility.next_level && (
        <section className="rounded-2xl border border-green-100 bg-green-50 p-5">
          <h2 className="text-sm font-semibold text-green-800">레벨업 도전 준비 완료!</h2>
          <p className="mt-1 text-xs text-green-600">
            {LEVEL_LABEL[eligibility.next_level] ?? eligibility.next_level} 레벨 시험에 응시할 수 있습니다.
          </p>
          <Link
            href="/level-up"
            className="mt-3 inline-block rounded-xl bg-green-700 px-4 py-2 text-xs font-semibold text-white hover:bg-green-800"
          >
            레벨업 시험 보기 →
          </Link>
        </section>
      )}

      {/* 배치 시험 CTA — placement_done=false 인 경우만 표시 */}
      {user && !user.placement_done && (
        <section className="rounded-2xl border border-blue-100 bg-blue-50 p-5">
          <h2 className="text-sm font-semibold text-blue-800">레벨 파악이 필요해요</h2>
          <p className="mt-1 text-xs text-blue-600">
            배치 시험을 통해 나에게 맞는 레벨로 시작하세요.
          </p>
          <Link
            href="/placement"
            className="mt-3 inline-block rounded-xl bg-blue-700 px-4 py-2 text-xs font-semibold text-white hover:bg-blue-800"
          >
            배치 시험 보기 →
          </Link>
        </section>
      )}

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

            <div className="mt-5 flex gap-2">
              {hasItems && (
                <Link
                  href="/study"
                  className="rounded-xl bg-neutral-900 px-5 py-2.5 text-sm font-semibold text-white hover:bg-neutral-700"
                >
                  학습 시작 →
                </Link>
              )}
              <Link
                href={`/study/review/${todayDate}`}
                className="rounded-xl border border-neutral-200 px-5 py-2.5 text-sm font-medium text-neutral-700 hover:border-neutral-400"
              >
                오늘 복습하기
              </Link>
            </div>

            {!hasItems && (
              <p className="mt-3 text-sm text-neutral-500">
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
