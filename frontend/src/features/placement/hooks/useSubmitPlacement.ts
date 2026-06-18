import { useMutation, useQueryClient } from "@tanstack/react-query";

import { submitPlacement } from "@/lib/api/backend";

export function useSubmitPlacement() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: submitPlacement,
    onSuccess: () => {
      // 레벨이 바뀌었으므로 auth 상태 및 study 관련 쿼리 무효화
      queryClient.invalidateQueries({ queryKey: ["motivation"] });
      queryClient.invalidateQueries({ queryKey: ["study", "session", "today"] });
      queryClient.invalidateQueries({ queryKey: ["study", "stats"] });
    },
  });
}
