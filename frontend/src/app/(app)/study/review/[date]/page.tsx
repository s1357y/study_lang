"use client";

// 날짜별 복습 페이지

import Link from "next/link";

import { ReviewSessionView } from "@/features/study/components/ReviewSessionView";
import { useSessionReview } from "@/features/study/hooks/useSessionReview";

type Params = { date: string };

export default function ReviewPage({ params }: { params: Params }) {
  const { date } = params;
  const { data, isLoading, error } = useSessionReview(date);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center gap-3">
        <Link href="/study/history" className="text-sm text-neutral-400 hover:text-neutral-600">
          ← 히스토리
        </Link>
        <h1 className="text-2xl font-bold">{date} 복습</h1>
      </div>

      {isLoading && (
        <p className="text-center text-sm text-neutral-400">불러오는 중…</p>
      )}

      {error && (
        <p className="text-center text-sm text-red-500">
          복습 데이터를 불러오지 못했습니다.
        </p>
      )}

      {data && <ReviewSessionView items={data} date={date} />}
    </div>
  );
}
