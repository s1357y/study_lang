import { useQuery } from "@tanstack/react-query";

import { fetchRecentSessions } from "@/lib/api/backend";

export function useRecentSessions(limit = 7) {
  return useQuery({
    queryKey: ["study", "sessions", "recent", limit],
    queryFn: () => fetchRecentSessions(limit),
    staleTime: 60_000,
  });
}
