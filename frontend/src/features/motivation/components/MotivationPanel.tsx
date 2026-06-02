"use client";

// 동기부여 패널 — 스트릭·레벨·XP·주간 목표를 한 번에 표시

import { useMotivation } from "../hooks/useMotivation";

function LevelXpBar({ xp, level }: { xp: number; level: number }) {
  // 현재 레벨 진입 XP: (level-1)^2 * 100 / 다음 레벨 진입 XP: level^2 * 100
  const levelStartXp = Math.pow(level - 1, 2) * 100;
  const levelEndXp = Math.pow(level, 2) * 100;
  const progress =
    levelEndXp > levelStartXp
      ? Math.min(100, ((xp - levelStartXp) / (levelEndXp - levelStartXp)) * 100)
      : 100;

  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center justify-between text-xs text-neutral-500">
        <span>Lv.{level}</span>
        <span>{xp} XP</span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-neutral-100">
        <div
          className="h-full rounded-full bg-violet-500 transition-all duration-500"
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  );
}

function WeeklyGoalBar({
  progressMinutes,
  goalMinutes,
}: {
  progressMinutes: number;
  goalMinutes: number;
}) {
  const pct = goalMinutes > 0 ? Math.min(100, (progressMinutes / goalMinutes) * 100) : 0;
  const achieved = pct >= 100;

  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center justify-between text-xs text-neutral-500">
        <span>주간 목표</span>
        <span>
          {progressMinutes}/{goalMinutes}분
          {achieved && <span className="ml-1 text-emerald-600">달성!</span>}
        </span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-neutral-100">
        <div
          className="h-full rounded-full bg-emerald-500 transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

export function MotivationPanel() {
  const { data, isLoading, error } = useMotivation();

  if (isLoading) {
    return (
      <section className="rounded-2xl border border-neutral-200 bg-white p-6">
        <p className="text-sm text-neutral-400">동기부여 정보 로딩 중…</p>
      </section>
    );
  }

  if (error || !data) return null;

  return (
    <section className="rounded-2xl border border-neutral-200 bg-white p-6">
      <h2 className="text-sm font-semibold text-neutral-700">나의 현황</h2>

      {/* 스트릭 */}
      <div className="mt-4 flex items-center gap-2">
        <span className="text-2xl">🔥</span>
        <div>
          <p className="text-xl font-bold tabular-nums">{data.streak_days}일</p>
          <p className="text-xs text-neutral-500">연속 학습</p>
        </div>
      </div>

      {/* 레벨·XP */}
      <div className="mt-4">
        <LevelXpBar xp={data.xp} level={data.level} />
      </div>

      {/* 주간 목표 */}
      <div className="mt-3">
        <WeeklyGoalBar
          progressMinutes={data.weekly_progress_minutes}
          goalMinutes={data.weekly_goal_minutes}
        />
      </div>
    </section>
  );
}
