"use client";

// 배치 시험 전체 흐름 — intro → testing → result 상태 머신

import { useRouter } from "next/navigation";
import { useState } from "react";

import { skipPlacement } from "@/lib/api/backend";
import { useAuth } from "@/lib/auth/AuthProvider";

import { usePlacement } from "../hooks/usePlacement";
import { useSubmitPlacement } from "../hooks/useSubmitPlacement";
import type { PlacementResult } from "../types";
import { PlacementResult as PlacementResultView } from "./PlacementResult";
import { StudyCard } from "@/features/study/components/StudyCard";
import type { ProblemOut } from "@/features/study/types";

type Phase = "intro" | "testing" | "result";

// PlacementProblem → ProblemOut 변환 (StudyCard 재사용)
function toStudyProblem(p: {
  problem_id: string;
  content_item_id: string;
  problem_type: string;
  prompt: string;
  answer: string;
  distractors: string[];
  tags: string[];
}): ProblemOut {
  return {
    problem_id: p.problem_id,
    content_item_id: p.content_item_id,
    problem_type: p.problem_type as ProblemOut["problem_type"],
    prompt: p.prompt,
    answer: p.answer,
    distractors: p.distractors,
    tags: p.tags,
  };
}

export function PlacementView() {
  const router = useRouter();
  const { state, updateUser } = useAuth();
  const { data, isLoading, error } = usePlacement();
  const submitMutation = useSubmitPlacement();

  const [phase, setPhase] = useState<Phase>("intro");
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, boolean>>({});
  const [result, setResult] = useState<PlacementResult | null>(null);
  const [isSkipping, setIsSkipping] = useState(false);

  async function handleSkip() {
    setIsSkipping(true);
    try {
      await skipPlacement();
      router.replace("/dashboard");
    } catch {
      // API 실패 시 버튼 복원 — redirect 하지 않음
      setIsSkipping(false);
    }
  }

  function handleStart() {
    setPhase("testing");
  }

  function handleNext(correct: boolean) {
    if (!data) return;
    const problem = data.problems[currentIndex];
    const newAnswers = { ...answers, [problem.problem_id]: correct };
    setAnswers(newAnswers);

    const isLast = currentIndex === data.problems.length - 1;
    if (isLast) {
      submitMutation.mutate(
        { placement_token: data.placement_token, answers: newAnswers },
        {
          onSuccess: (res) => {
            // 배치 완료 즉시 auth 상태 갱신 — 대시보드가 새 레벨을 바로 반영하도록
            if (state.status === "authenticated") {
              updateUser({ ...state.user, level: res.assigned_level, placement_done: true });
            }
            setResult(res);
            setPhase("result");
          },
        },
      );
    } else {
      setCurrentIndex((i) => i + 1);
    }
  }

  if (phase === "result" && result) {
    return (
      <div className="mx-auto max-w-lg">
        <PlacementResultView result={result} />
      </div>
    );
  }

  if (phase === "testing") {
    if (isLoading || !data) {
      return <p className="text-center text-sm text-neutral-400">문제를 불러오는 중…</p>;
    }
    const problem = data.problems[currentIndex];
    return (
      <div className="mx-auto max-w-lg">
        <div className="mb-4 flex items-center justify-between text-sm text-neutral-500">
          <span>배치 시험</span>
          <span>
            {currentIndex + 1} / {data.total}
          </span>
        </div>
        <div className="mb-2 h-1.5 w-full overflow-hidden rounded-full bg-neutral-100">
          <div
            className="h-full rounded-full bg-neutral-900 transition-all"
            style={{ width: `${((currentIndex + 1) / data.total) * 100}%` }}
          />
        </div>
        {submitMutation.isPending ? (
          <p className="mt-8 text-center text-sm text-neutral-400">결과를 계산하는 중…</p>
        ) : (
          <StudyCard
            key={problem.problem_id}
            problem={toStudyProblem(problem)}
            onNext={(correct) => handleNext(correct)}
          />
        )}
      </div>
    );
  }

  // intro
  return (
    <div className="mx-auto max-w-lg">
      <div className="rounded-2xl border border-neutral-200 bg-white p-8">
        <h2 className="text-xl font-bold">배치 시험</h2>
        <p className="mt-3 text-sm text-neutral-600 leading-relaxed">
          다양한 난이도의 문제를 통해 현재 일본어 실력을 파악합니다.
          결과에 따라 맞춤 레벨이 자동으로 배정됩니다.
        </p>
        <ul className="mt-4 space-y-2 text-sm text-neutral-500">
          <li>• 최대 20문제 (레벨별 최대 5문제)</li>
          <li>• 객관식 혼합, 평균 5~10분 소요</li>
          <li>• 완료 후 레벨업 시험으로 레벨을 높일 수 있습니다</li>
        </ul>

        {error && (
          <p className="mt-4 text-sm text-red-500">
            문제를 불러오지 못했습니다. 잠시 후 다시 시도해주세요.
          </p>
        )}

        <div className="mt-6 flex gap-3">
          <button
            onClick={handleStart}
            disabled={isLoading || !!error}
            className="flex-1 rounded-xl bg-neutral-900 py-3 text-sm font-semibold text-white hover:bg-neutral-700 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {isLoading ? "불러오는 중…" : "시험 시작"}
          </button>
          <button
            onClick={handleSkip}
            disabled={isSkipping}
            className="rounded-xl border border-neutral-200 px-4 py-3 text-sm text-neutral-500 hover:border-neutral-400 disabled:cursor-not-allowed disabled:opacity-40"
          >
            건너뛰기
          </button>
        </div>
      </div>
    </div>
  );
}
