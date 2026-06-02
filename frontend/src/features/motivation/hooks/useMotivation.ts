// 동기부여 지표 조회 훅 — 대시보드·헤더에서 사용
import { useQuery } from "@tanstack/react-query";
import { fetchMotivation } from "@/lib/api/backend";

export function useMotivation() {
  return useQuery({
    queryKey: ["motivation"],
    queryFn: fetchMotivation,
    staleTime: 60_000,   // 1분 — 시도 제출 후 invalidate 로 갱신
  });
}
