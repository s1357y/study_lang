"use client";

// 레벨업 시험 라우트 페이지 — 응시 자격 확인 후 시험 컴포넌트로 분기.

import Link from "next/link";

import { LevelUpExamView } from "@/features/level-up/components/LevelUpExamView";
import { useLevelUpEligibility } from "@/features/level-up/hooks/useLevelUpEligibility";
import { useAuth } from "@/lib/auth/AuthProvider";

export default function LevelUpPage() {
  const { data, isLoading, error } = useLevelUpEligibility();
  const { state } = useAuth();
  const fromLevel =
    state.status === "authenticated" ? state.user.level : "BEGINNER";

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-24 text-sm text-neutral-400">
        자격 확인 중…
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-sm text-red-700">
        정보를 불러오지 못했습니다. 페이지를 새로고침 해주세요.
      </div>
    );
  }

  if (!data.eligible) {
    return (
      <div className="mx-auto max-w-lg">
        <div className="rounded-2xl border border-neutral-200 bg-white p-8">
          <h2 className="text-xl font-bold">레벨업 시험</h2>
          <p className="mt-4 text-sm text-neutral-600 leading-relaxed">
            아직 응시 자격이 없습니다.
          </p>
          <ul className="mt-3 space-y-1 text-sm text-neutral-500">
            <li>
              • 현재 레벨 학습량: {data.studied_count} / {data.required_count}개
            </li>
            {data.cooldown_until && (
              <li>
                • 재응시 가능 시각:{" "}
                {new Date(data.cooldown_until).toLocaleString("ko-KR")}
              </li>
            )}
          </ul>
          <Link
            href="/dashboard"
            className="mt-6 inline-block rounded-xl border border-neutral-200 px-5 py-2.5 text-sm font-medium text-neutral-700 hover:border-neutral-400"
          >
            대시보드로
          </Link>
        </div>
      </div>
    );
  }

  return (
    <LevelUpExamView
      fromLevel={fromLevel}
      toLevel={data.next_level ?? fromLevel}
    />
  );
}
