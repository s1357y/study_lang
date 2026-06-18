// 레벨업 시험 문제 발급 훅 — 자격이 있을 때만 호출.

import { useQuery } from "@tanstack/react-query";

import { fetchLevelUpProblems } from "@/lib/api/backend";

export function useLevelUpExam(enabled: boolean) {
  return useQuery({
    queryKey: ["level-up", "problems"],
    queryFn: fetchLevelUpProblems,
    enabled,
    staleTime: 20 * 60_000, // 토큰 만료(30분) 이전에 재발급 방지
    refetchOnWindowFocus: false,
  });
}
