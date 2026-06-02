"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { AuthForm } from "@/features/auth/AuthForm";
import { useAuth } from "@/lib/auth/AuthProvider";

export default function SignInPage() {
  const router = useRouter();
  const { state, login } = useAuth();

  // 이미 로그인된 상태로 진입하면 대시보드로 자동 이동
  useEffect(() => {
    if (state.status === "authenticated") router.replace("/dashboard");
  }, [state.status, router]);

  return (
    <AuthForm
      title="로그인"
      submitLabel="로그인"
      onSubmit={async (email, password) => {
        await login(email, password);
        router.replace("/dashboard");
      }}
      footer={
        <span>
          계정이 없으신가요?{" "}
          <Link href="/sign-up" className="underline">
            회원가입
          </Link>
        </span>
      }
    />
  );
}
