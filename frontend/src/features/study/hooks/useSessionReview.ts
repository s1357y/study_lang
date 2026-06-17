import { useQuery } from "@tanstack/react-query";

import { fetchSessionReview } from "@/lib/api/backend";

export function useSessionReview(date: string) {
  return useQuery({
    queryKey: ["study", "review", date],
    queryFn: () => fetchSessionReview(date),
    staleTime: 10 * 60 * 1000, // 10분
    enabled: !!date,
  });
}
