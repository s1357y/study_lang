import { useMutation } from "@tanstack/react-query";

import { submitAttempt, type SubmitAttemptBody } from "@/lib/api/backend";
import { AttemptResultSchema } from "../types";

export function useSubmitAttempt() {
  return useMutation({
    mutationFn: async (body: SubmitAttemptBody) => {
      const raw = await submitAttempt(body);
      return AttemptResultSchema.parse(raw);
    },
  });
}
