"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { AuthForm } from "@/features/auth/AuthForm";
import { useAuth } from "@/lib/auth/AuthProvider";

export default function SignUpPage() {
  const router = useRouter();
  const { state, register } = useAuth();

  useEffect(() => {
    if (state.status === "authenticated") router.replace("/dashboard");
  }, [state.status, router]);

  return (
    <AuthForm
      title="회원가입"
      submitLabel="회원가입"
      onSubmit={async (email, password) => {
        await register(email, password);
        // 신규 가입 → 배치 시험으로 이동
        router.replace("/placement");
      }}
      footer={
        <span>
          이미 계정이 있으신가요?{" "}
          <Link href="/sign-in" className="underline">
            로그인
          </Link>
        </span>
      }
    />
  );
}
