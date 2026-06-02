import { useQuery } from "@tanstack/react-query";

import { fetchTodaySession } from "@/lib/api/backend";
import { StudySessionSchema } from "../types";

export function useStudySession() {
  return useQuery({
    queryKey: ["study", "session", "today"],
    queryFn: async () => {
      const raw = await fetchTodaySession();
      return StudySessionSchema.parse(raw);
    },
    // 세션은 하루 단위로 생성되므로 긴 staleTime
    staleTime: 5 * 60_000,
    refetchOnWindowFocus: false,
  });
}
