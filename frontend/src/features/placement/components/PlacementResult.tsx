"use client";

// 배치 시험 결과 화면 — 배정 레벨 표시 + 학습 시작 버튼

import Link from "next/link";

import type { PlacementResult } from "../types";

type Props = {
  result: PlacementResult;
};

export function PlacementResult({ result }: Props) {
  return (
    <div className="flex flex-col items-center gap-6 text-center">
      <div className="flex h-20 w-20 items-center justify-center rounded-full bg-neutral-900 text-3xl text-white">
        🎯
      </div>

      <div>
        <p className="text-sm text-neutral-500">배정된 레벨</p>
        <p className="mt-1 text-2xl font-bold">{result.level_label}</p>
        <p className="mt-2 text-sm text-neutral-600">{result.message}</p>
      </div>

      <Link
        href="/dashboard"
        className="mt-2 inline-block rounded-xl bg-neutral-900 px-8 py-3 text-sm font-semibold text-white hover:bg-neutral-700"
      >
        학습 시작 →
      </Link>
    </div>
  );
}
