"use client";

// 문제 카드 — MCQ(객관식) 또는 입력식 문제를 렌더링.
// answering 단계에서 답을 고르거나 입력하고 제출 → revealed 단계에서 결과 표시 → 다음 버튼으로 진행.

import { useMemo, useRef, useState } from "react";

import type { ProblemOut } from "../types";

const PROMPT_LABEL: Record<string, string> = {
  mcq_meaning: "의미를 고르세요",
  mcq_reading: "읽기를 고르세요",
  fill_blank: "빈칸을 채우세요",
  short_answer: "답을 입력하세요",
  translation: "번역하세요",
  listening: "들은 내용을 입력하세요",
};

type Props = {
  problem: ProblemOut;
  onNext: (correct: boolean, responseTimeMs: number) => void;
};

function shuffleChoices(answer: string, distractors: string[]): string[] {
  // Fisher-Yates 셔플 — 매 렌더마다 재실행되지 않도록 useMemo 에 감쌈
  const arr = [answer, ...distractors];
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
  return arr;
}

export function StudyCard({ problem, onNext }: Props) {
  const startTimeRef = useRef(Date.now());
  const isMcq =
    problem.problem_type === "mcq_meaning" ||
    problem.problem_type === "mcq_reading";

  // problem_id 가 바뀔 때(= key 교체) 자동 재마운트되므로 셔플은 최초 1회만
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const choices = useMemo(() => shuffleChoices(problem.answer, problem.distractors), []);

  const [selected, setSelected] = useState<string | null>(null);
  const [inputValue, setInputValue] = useState("");
  const [phase, setPhase] = useState<"answering" | "revealed">("answering");
  const [isCorrect, setIsCorrect] = useState(false);
  const [elapsedMs, setElapsedMs] = useState(0);

  const canSubmit = isMcq ? selected !== null : inputValue.trim().length > 0;

  function handleSubmit() {
    const userAnswer = isMcq ? (selected ?? "") : inputValue.trim();
    const correct =
      userAnswer.toLowerCase().trim() === problem.answer.toLowerCase().trim();
    const elapsed = Date.now() - startTimeRef.current;
    setIsCorrect(correct);
    setElapsedMs(elapsed);
    setPhase("revealed");
  }

  if (phase === "revealed") {
    return (
      <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm">
        <p className="text-sm text-neutral-500">
          {PROMPT_LABEL[problem.problem_type] ?? "문제"}
        </p>
        <p className="mt-2 text-xl font-bold">{problem.prompt}</p>

        <div
          className={`mt-4 rounded-xl p-4 ${isCorrect ? "bg-green-50" : "bg-red-50"}`}
        >
          <p
            className={`text-sm font-semibold ${isCorrect ? "text-green-700" : "text-red-700"}`}
          >
            {isCorrect ? "정답입니다!" : "오답입니다"}
          </p>
          {!isCorrect && (
            <p className="mt-1 text-sm text-neutral-700">
              정답: <span className="font-semibold">{problem.answer}</span>
            </p>
          )}
        </div>

        <button
          onClick={() => onNext(isCorrect, elapsedMs)}
          className="mt-6 w-full rounded-xl bg-neutral-900 py-3 text-sm font-semibold text-white hover:bg-neutral-700"
        >
          다음
        </button>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm">
      <p className="text-sm text-neutral-500">
        {PROMPT_LABEL[problem.problem_type] ?? "문제"}
      </p>
      <p className="mt-2 text-xl font-bold">{problem.prompt}</p>

      {isMcq ? (
        <ul className="mt-4 flex flex-col gap-2">
          {choices.map((choice) => (
            <li key={choice}>
              <button
                onClick={() => setSelected(choice)}
                className={`w-full rounded-xl border px-4 py-3 text-left text-sm transition-colors ${
                  selected === choice
                    ? "border-neutral-900 bg-neutral-900 text-white"
                    : "border-neutral-200 bg-white hover:border-neutral-400"
                }`}
              >
                {choice}
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <input
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && canSubmit) handleSubmit();
          }}
          placeholder="입력하세요"
          className="mt-4 w-full rounded-xl border border-neutral-200 px-4 py-3 text-sm focus:border-neutral-900 focus:outline-none"
          autoFocus
        />
      )}

      <button
        onClick={handleSubmit}
        disabled={!canSubmit}
        className="mt-4 w-full rounded-xl bg-neutral-900 py-3 text-sm font-semibold text-white hover:bg-neutral-700 disabled:cursor-not-allowed disabled:opacity-40"
      >
        제출
      </button>
    </div>
  );
}
