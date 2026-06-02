import type { Metadata } from "next";

import { AuthProvider } from "@/lib/auth/AuthProvider";
import { QueryProvider } from "@/lib/query/QueryProvider";

import "./globals.css";

export const metadata: Metadata = {
  title: "LingoLab",
  description: "AI 기반 개인화 일본어 학습 플랫폼",
};

// 루트 레이아웃은 서버 컴포넌트로 유지하고, 인증·쿼리 컨텍스트만 클라이언트 트리에서 제공.
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ko">
      <body className="min-h-screen bg-neutral-50 text-neutral-900 antialiased">
        <QueryProvider>
          <AuthProvider>{children}</AuthProvider>
        </QueryProvider>
      </body>
    </html>
  );
}
