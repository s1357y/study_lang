// 오늘의 학습 세션 페이지 — StudySessionView 가 데이터 로딩과 UI 를 담당한다.

import { StudySessionView } from "@/features/study/components/StudySessionView";

export default function StudyPage() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold">오늘의 학습</h1>
        <p className="mt-1 text-sm text-neutral-500">
          복습 문제와 새 단어를 풀어보세요
        </p>
      </div>
      <StudySessionView />
    </div>
  );
}
