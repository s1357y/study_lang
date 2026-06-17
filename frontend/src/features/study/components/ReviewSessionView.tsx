"use client";

// 복습 세션 뷰 — 진행 바 + 플래시카드 + 이전/다음 + 요약 통계

import { useState } from "react";

import type { ReviewItem } from "../types";
import { ReviewFlashCard } from "./ReviewFlashCard";

type Props = {
  items: ReviewItem[];
  date: string;
};

export function ReviewSessionView({ items, date }: Props) {
  const [index, setIndex] = useState(0);

  if (items.length === 0) {
    return (
      <p className="text-center text-sm text-neutral-400">
        {date}에 완료한 문제가 없습니다.
      </p>
    );
  }

  // 요약 통계
  const correct = items.filter((i) => i.my_correct === true).length;
  const wrong = items.filter((i) => i.my_correct === false).length;
  const notAttempted = items.filter((i) => i.my_correct === null).length;

  const current = items[index];
  const pct = Math.round(((index + 1) / items.length) * 100);

  return (
    <div className="flex flex-col gap-4">
      {/* 진행 바 */}
      <div>
        <div className="mb-1 flex justify-between text-xs text-neutral-500">
          <span>
            {index + 1} / {items.length}
          </span>
          <span>{date}</span>
        </div>
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-neutral-100">
          <div
            className="h-full rounded-full bg-neutral-900 transition-all"
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>

      {/* 플래시카드 */}
      <ReviewFlashCard key={current.problem_id} item={current} />

      {/* 이전/다음 */}
      <div className="flex gap-2">
        <button
          onClick={() => setIndex((i) => Math.max(0, i - 1))}
          disabled={index === 0}
          className="flex-1 rounded-xl border border-neutral-200 py-2.5 text-sm font-medium text-neutral-700 hover:border-neutral-400 disabled:cursor-not-allowed disabled:opacity-40"
        >
          이전
        </button>
        <button
          onClick={() => setIndex((i) => Math.min(items.length - 1, i + 1))}
          disabled={index === items.length - 1}
          className="flex-1 rounded-xl bg-neutral-900 py-2.5 text-sm font-semibold text-white hover:bg-neutral-700 disabled:cursor-not-allowed disabled:opacity-40"
        >
          다음
        </button>
      </div>

      {/* 처음부터 버튼 */}
      {index === items.length - 1 && (
        <button
          onClick={() => setIndex(0)}
          className="text-center text-sm text-neutral-400 underline hover:text-neutral-600"
        >
          처음부터 다시 보기
        </button>
      )}

      {/* 요약 통계 */}
      <div className="mt-2 rounded-xl border border-neutral-100 bg-neutral-50 p-4">
        <p className="mb-2 text-xs font-medium text-neutral-500">이 세션 결과</p>
        <div className="flex gap-4 text-sm">
          <span className="text-green-700">정답 {correct}개</span>
          <span className="text-red-700">오답 {wrong}개</span>
          {notAttempted > 0 && (
            <span className="text-neutral-400">미시도 {notAttempted}개</span>
          )}
        </div>
      </div>
    </div>
  );
}
