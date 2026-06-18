// 레벨업 시험 답안 제출 훅.

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { submitLevelUp } from "@/lib/api/backend";

export function useSubmitLevelUp() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: submitLevelUp,
    onSuccess: () => {
      // 레벨 변경 후 관련 캐시 전체 무효화 — eligibility·학습 세션·통계·모티베이션 stale 방지
      queryClient.invalidateQueries({ queryKey: ["level-up", "eligibility"] });
      queryClient.invalidateQueries({ queryKey: ["study", "session", "today"] });
      queryClient.invalidateQueries({ queryKey: ["study", "stats"] });
      queryClient.invalidateQueries({ queryKey: ["motivation"] });
    },
  });
}
