import { useQuery } from "@tanstack/react-query";

import { fetchPlacementProblems } from "@/lib/api/backend";

export function usePlacement() {
  return useQuery({
    queryKey: ["placement", "problems"],
    queryFn: fetchPlacementProblems,
    // 시험 중 window focus 로 재요청하지 않음
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  });
}
