"use client";

// 레벨업 시험 전체 흐름 — intro → testing → result.
// PlacementView 와 동일한 상태 머신 구조를 재사용한다.

import { useState } from "react";

import { StudyCard } from "@/features/study/components/StudyCard";
import type { ProblemOut } from "@/features/study/types";
import type { LevelUpResult } from "@/lib/api/backend";
import { useAuth } from "@/lib/auth/AuthProvider";

import { useLevelUpExam } from "../hooks/useLevelUpExam";
import { useSubmitLevelUp } from "../hooks/useSubmitLevelUp";
import { LevelUpResultView } from "./LevelUpResult";

type Phase = "intro" | "testing" | "result";

const LEVEL_LABEL: Record<string, string> = {
  BEGINNER: "N5",
  ELEMENTARY: "N4",
  INTERMEDIATE: "N3",
  ADVANCED: "N2",
};

function toProblemOut(p: {
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

export function LevelUpExamView({
  fromLevel,
  toLevel,
}: {
  fromLevel: string;
  toLevel: string;
}) {
  const { state, updateUser } = useAuth();
  const [phase, setPhase] = useState<Phase>("intro");
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, boolean>>({});
  const [result, setResult] = useState<LevelUpResult | null>(null);

  const { data, isLoading, error } = useLevelUpExam(phase === "testing" || phase === "intro");
  const submitMutation = useSubmitLevelUp();

  function handleNext(correct: boolean) {
    if (!data) return;
    const problem = data.problems[currentIndex];
    const newAnswers = { ...answers, [problem.problem_id]: correct };
    setAnswers(newAnswers);

    const isLast = currentIndex === data.problems.length - 1;
    if (isLast) {
      submitMutation.mutate(
        { level_up_token: data.level_up_token, answers: newAnswers },
        {
          onSuccess: (res) => {
            if (res.passed && state.status === "authenticated") {
              updateUser({ ...state.user, level: res.to_level });
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
        <LevelUpResultView result={result} />
      </div>
    );
  }

  if (phase === "testing") {
    if (isLoading || !data) {
      return <p className="text-center text-sm text-neutral-400">문제를 불러오는 중…</p>;
    }
    if (error) {
      return (
        <p className="text-center text-sm text-red-500">
          문제를 불러오지 못했습니다. 페이지를 새로고침 해주세요.
        </p>
      );
    }
    const problem = data.problems[currentIndex];
    return (
      <div className="mx-auto max-w-lg">
        <div className="mb-4 flex items-center justify-between text-sm text-neutral-500">
          <span>
            레벨업 시험 ({LEVEL_LABEL[fromLevel] ?? fromLevel} →{" "}
            {LEVEL_LABEL[toLevel] ?? toLevel})
          </span>
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
            problem={toProblemOut(problem)}
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
        <h2 className="text-xl font-bold">레벨업 시험</h2>
        <p className="mt-2 text-sm text-neutral-500">
          {LEVEL_LABEL[fromLevel] ?? fromLevel} → {LEVEL_LABEL[toLevel] ?? toLevel} 승급 도전
        </p>
        <p className="mt-3 text-sm text-neutral-600 leading-relaxed">
          실제 JLPT 형식으로 출제됩니다. 문자·어휘·문법 영역을 포함한 총 20문제이며,
          70% 이상 정답 시 다음 레벨로 승급합니다.
        </p>
        <ul className="mt-4 space-y-1 text-sm text-neutral-500">
          <li>• 총 20문제 (문자·어휘·문법 혼합)</li>
          <li>• 70% 이상 정답 시 합격</li>
          <li>• 불합격 시 7일 후 재응시 가능</li>
        </ul>

        {error && (
          <p className="mt-4 text-sm text-red-500">
            문제를 불러오지 못했습니다. 잠시 후 다시 시도해주세요.
          </p>
        )}

        <button
          onClick={() => setPhase("testing")}
          disabled={isLoading || !!error}
          className="mt-6 w-full rounded-xl bg-neutral-900 py-3 text-sm font-semibold text-white hover:bg-neutral-700 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {isLoading ? "불러오는 중…" : "시험 시작"}
        </button>
      </div>
    </div>
  );
}
