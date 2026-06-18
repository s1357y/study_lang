// 레벨업 시험 답안 제출 훅.

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { submitLevelUp } from "@/lib/api/backend";

export function useSubmitLevelUp() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: submitLevelUp,
    onSuccess: () => {
      // 자격 캐시 무효화 — 합격 후 배너 즉시 숨김
      queryClient.invalidateQueries({ queryKey: ["level-up", "eligibility"] });
    },
  });
}
