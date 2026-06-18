// 오늘 세션에 추가 문제를 요청하는 mutation 훅.
// 성공 시 캐시를 새 세션 데이터로 교체해 리렌더 없이 문제 목록을 갱신한다.

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { extendTodaySession } from "@/lib/api/backend";
import { StudySessionSchema } from "../types";

export function useExtendSession() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const raw = await extendTodaySession();
      return StudySessionSchema.parse(raw);
    },
    onSuccess: (extended) => {
      // 세션 캐시를 서버 응답으로 교체 — currentIndex 는 로컬 state 이므로 영향 없음
      queryClient.setQueryData(["study", "session", "today"], extended);
    },
  });
}
