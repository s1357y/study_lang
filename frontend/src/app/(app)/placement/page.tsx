"use client";

// 배치 시험 페이지 — (app) 그룹 내이므로 인증 가드 자동 적용

import { PlacementView } from "@/features/placement/components/PlacementView";

export default function PlacementPage() {
  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-bold">배치 시험</h1>
      <PlacementView />
    </div>
  );
}
