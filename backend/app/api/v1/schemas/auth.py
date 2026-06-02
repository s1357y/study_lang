"""인증 라우트의 Pydantic 요청/응답 스키마."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    # 이메일 형식은 pydantic 의 EmailStr 로 검증, 비밀번호는 최소 길이만
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserPublic(BaseModel):
    # 외부 노출용 사용자 표현 — password_hash 등 민감 정보는 절대 포함하지 않음
    id: UUID
    email: EmailStr
    target_language: str
    level: str

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    # refresh 는 쿠키로 나가므로 본문에는 access 만
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserPublic
