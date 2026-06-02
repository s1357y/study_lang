import { useQuery } from "@tanstack/react-query";

import { fetchStudyStats } from "@/lib/api/backend";
import { StudyStatsSchema } from "../types";

export function useStudyStats() {
  return useQuery({
    queryKey: ["study", "stats"],
    queryFn: async () => {
      const raw = await fetchStudyStats();
      return StudyStatsSchema.parse(raw);
    },
    staleTime: 30_000,
  });
}
