"use client";

// 오늘 학습 세션 전체 흐름 컨트롤러.
// 세션 로드 → 문제 순회 → 완료 화면 세 가지 상태를 관리한다.

import Link from "next/link";
import { useState } from "react";

import { useStudySession } from "../hooks/useStudySession";
import { useExtendSession } from "../hooks/useExtendSession";
import { useSubmitAttempt } from "../hooks/useSubmitAttempt";
import type { StudySession } from "../types";
import { StudyCard } from "./StudyCard";

function CompletionScreen({
  total,
  onExtend,
  isExtending,
  extendFailed,
}: {
  total: number;
  onExtend: () => void;
  isExtending: boolean;
  extendFailed: boolean;
}) {
  return (
    <div className="flex flex-col items-center gap-4 py-16 text-center">
      <p className="text-4xl font-bold text-neutral-900">완료!</p>
      <p className="text-neutral-600">오늘 {total}문제를 모두 풀었습니다.</p>
      {extendFailed ? (
        <p className="mt-2 text-sm text-neutral-500">
          지금은 추가 콘텐츠를 준비 중입니다.
        </p>
      ) : (
        <button
          onClick={onExtend}
          disabled={isExtending}
          className="mt-2 rounded-xl bg-neutral-100 px-6 py-3 text-sm font-semibold text-neutral-900 hover:bg-neutral-200 disabled:opacity-40"
        >
          {isExtending ? "불러오는 중…" : "더 공부하기"}
        </button>
      )}
      <Link
        href="/dashboard"
        className="mt-4 rounded-xl bg-neutral-900 px-6 py-3 text-sm font-semibold text-white hover:bg-neutral-700"
      >
        대시보드로
      </Link>
    </div>
  );
}

function EmptySessionScreen() {
  return (
    <div className="flex flex-col items-center gap-4 py-16 text-center">
      <p className="text-2xl font-bold text-neutral-900">오늘 학습 끝!</p>
      <p className="text-neutral-600">
        복습할 단어와 새 단어가 없습니다. 내일 다시 확인하세요.
      </p>
      <Link
        href="/dashboard"
        className="mt-4 rounded-xl border border-neutral-300 px-6 py-3 text-sm font-semibold hover:bg-neutral-50"
      >
        대시보드로
      </Link>
    </div>
  );
}

function SessionInner({ session }: { session: StudySession }) {
  // completed_count 에서 시작 — 이미 완료한 문제는 스킵
  const [currentIndex, setCurrentIndex] = useState(session.completed_count);
  const submitAttemptMutation = useSubmitAttempt();
  const extendMutation = useExtendSession();

  const total = session.problems.length;

  if (total === 0) return <EmptySessionScreen />;
  if (currentIndex >= total)
    return (
      <CompletionScreen
        total={total}
        onExtend={() => extendMutation.mutate()}
        isExtending={extendMutation.isPending}
        extendFailed={extendMutation.isError}
      />
    );

  const currentProblem = session.problems[currentIndex];

  function handleNext(correct: boolean, responseTimeMs: number) {
    submitAttemptMutation.mutate({
      problem_id: currentProblem.problem_id,
      content_item_id: currentProblem.content_item_id,
      correct,
      response_time_ms: responseTimeMs,
    });
    setCurrentIndex((i) => i + 1);
  }

  return (
    <div className="flex flex-col gap-4">
      {/* 진행 바 */}
      <div className="flex items-center gap-3">
        <div className="h-2 flex-1 overflow-hidden rounded-full bg-neutral-100">
          <div
            className="h-full rounded-full bg-neutral-900 transition-all duration-300"
            style={{ width: `${(currentIndex / total) * 100}%` }}
          />
        </div>
        <span className="text-xs tabular-nums text-neutral-500">
          {currentIndex}/{total}
        </span>
      </div>

      <StudyCard
        key={currentProblem.problem_id}
        problem={currentProblem}
        onNext={handleNext}
      />
    </div>
  );
}

export function StudySessionView() {
  const { data: session, isLoading, error } = useStudySession();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-24 text-sm text-neutral-500">
        세션 불러오는 중…
      </div>
    );
  }

  if (error || !session) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-sm text-red-700">
        세션을 불러오지 못했습니다. 페이지를 새로고침 해주세요.
      </div>
    );
  }

  return <SessionInner session={session} />;
}
