import { useMutation, useQueryClient } from "@tanstack/react-query";

import { submitAttempt, type SubmitAttemptBody } from "@/lib/api/backend";
import { AttemptResultSchema } from "../types";

export function useSubmitAttempt() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: SubmitAttemptBody) => {
      const raw = await submitAttempt(body);
      return AttemptResultSchema.parse(raw);
    },
    // 시도 제출 후 세션 캐시 무효화 — 5분 staleTime 으로 인한 completed_count 불일치 방지
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["study", "session", "today"] });
    },
  });
}
