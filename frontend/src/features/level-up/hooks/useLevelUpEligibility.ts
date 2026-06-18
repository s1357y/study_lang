// 레벨업 시험 응시 자격 조회 훅 — 창 포커스 시 재조회해 최신 학습 현황 반영.

import { useQuery } from "@tanstack/react-query";

import { fetchLevelUpEligibility } from "@/lib/api/backend";

export function useLevelUpEligibility() {
  return useQuery({
    queryKey: ["level-up", "eligibility"],
    queryFn: fetchLevelUpEligibility,
    staleTime: 60_000,
    refetchOnWindowFocus: true,
  });
}
