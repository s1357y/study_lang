"use client";

// 복습 플래시카드 — 탭으로 앞/뒤 전환, my_correct 배지 표시

import { useState } from "react";

import type { ReviewItem } from "../types";

type Props = {
  item: ReviewItem;
};

const CORRECT_LABEL: Record<string, string> = {
  true: "정답",
  false: "오답",
};

function CorrectBadge({ correct }: { correct: boolean | null }) {
  if (correct === null) {
    return (
      <span className="rounded-full bg-neutral-100 px-2 py-0.5 text-xs text-neutral-500">
        미시도
      </span>
    );
  }
  return (
    <span
      className={`rounded-full px-2 py-0.5 text-xs font-medium ${
        correct ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"
      }`}
    >
      {CORRECT_LABEL[String(correct)]}
    </span>
  );
}

export function ReviewFlashCard({ item }: Props) {
  const [flipped, setFlipped] = useState(false);

  return (
    <button
      onClick={() => setFlipped((f) => !f)}
      className="w-full cursor-pointer rounded-2xl border border-neutral-200 bg-white p-6 text-left shadow-sm transition-shadow hover:shadow-md"
    >
      {!flipped ? (
        // 앞면 — 문제
        <div className="flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <span className="text-xs text-neutral-400">탭하여 답 확인</span>
            <CorrectBadge correct={item.my_correct} />
          </div>
          <p className="text-xl font-bold">{item.prompt}</p>
          {item.tags.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {item.tags.map((tag) => (
                <span
                  key={tag}
                  className="rounded-full bg-neutral-100 px-2 py-0.5 text-xs text-neutral-500"
                >
                  {tag}
                </span>
              ))}
            </div>
          )}
        </div>
      ) : (
        // 뒷면 — 답 + 상세 정보
        <div className="flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <span className="text-xs text-neutral-400">탭하여 문제로</span>
            <CorrectBadge correct={item.my_correct} />
          </div>
          <p className="text-xl font-bold text-neutral-900">{item.answer}</p>
          {item.payload.reading && item.payload.reading !== item.answer && (
            <p className="text-sm text-neutral-500">읽기: {item.payload.reading}</p>
          )}
          {item.payload.meaning_ko && (
            <p className="text-sm text-neutral-700">{item.payload.meaning_ko}</p>
          )}
          {item.payload.example_ja && (
            <div className="rounded-xl bg-neutral-50 p-3 text-sm">
              <p className="text-neutral-700">{item.payload.example_ja}</p>
              {item.payload.example_ko && (
                <p className="mt-1 text-neutral-400">{item.payload.example_ko}</p>
              )}
            </div>
          )}
        </div>
      )}
    </button>
  );
}
