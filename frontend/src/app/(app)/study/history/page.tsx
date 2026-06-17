"use client";

// 학습 히스토리 페이지 — 최근 세션 목록 + 날짜별 복습 링크

import Link from "next/link";

import { useRecentSessions } from "@/features/study/hooks/useRecentSessions";

export default function HistoryPage() {
  const { data, isLoading, error } = useRecentSessions(14);

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-bold">학습 히스토리</h1>

      {isLoading && (
        <p className="text-sm text-neutral-400">불러오는 중…</p>
      )}

      {error && (
        <p className="text-sm text-red-500">히스토리를 불러오지 못했습니다.</p>
      )}

      {data && data.length === 0 && (
        <p className="text-sm text-neutral-400">아직 학습 기록이 없습니다.</p>
      )}

      {data && data.length > 0 && (
        <div className="flex flex-col gap-2">
          {data.map((session) => (
            <div
              key={session.id}
              className="flex items-center justify-between rounded-xl border border-neutral-200 bg-white p-4"
            >
              <div>
                <p className="text-sm font-semibold">{session.date}</p>
                <p className="mt-0.5 text-xs text-neutral-500">
                  {session.completed_count} / {session.total_count}개 완료
                </p>
              </div>
              <Link
                href={`/study/review/${session.date}`}
                className="rounded-lg bg-neutral-100 px-3 py-1.5 text-xs font-medium text-neutral-700 hover:bg-neutral-200"
              >
                복습하기
              </Link>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
