"""인증 비즈니스 흐름 — 회원가입 / 로그인 / 토큰 회전 / 로그아웃.

이 모듈만이 토큰 발급 책임을 가진다. routes 는 여기 함수를 호출하기만 한다.
정책 상세는 docs/auth-flow.md 와 backend/rules/auth-flow.md 참조.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    InvalidTokenError,
    decode_refresh,
    encode_access,
    encode_refresh,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.repositories import refresh_token_repo, user_repo


class AuthError(Exception):
    """인증 실패의 도메인 예외. routes 가 401/409 등으로 매핑한다."""

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    access_expires_in: int
    refresh_expires_in: int


# ============================================================================
# 내부 헬퍼
# ============================================================================


def _hash_token(token: str) -> str:
    # 평문 refresh 는 저장하지 않고 sha256 해시만 보관
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def _issue_pair(
    db: AsyncSession,
    *,
    user_id: UUID,
    family_id: UUID,
    parent_id: UUID | None,
) -> TokenPair:
    # access 발급 (메모리/응답 본문용)
    access = encode_access(str(user_id))

    # refresh 발급 — 같은 family 안에서 회전 추적
    refresh_token, jti_str = encode_refresh(str(user_id), family_id=str(family_id))
    jti = UUID(jti_str)
    # expires_at 은 encode_refresh 가 이미 알고 있는 TTL 로 직접 계산 (re-decode 불필요)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=settings.jwt_refresh_ttl_seconds)

    # DB 에 해시만 기록 — 평문 토큰은 응답에만 실어 보냄
    await refresh_token_repo.create(
        db,
        jti=jti,
        user_id=user_id,
        token_hash=_hash_token(refresh_token),
        family_id=family_id,
        expires_at=expires_at,
        parent_id=parent_id,
    )

    return TokenPair(
        access_token=access,
        refresh_token=refresh_token,
        access_expires_in=settings.jwt_access_ttl_seconds,
        refresh_expires_in=settings.jwt_refresh_ttl_seconds,
    )


# ============================================================================
# 회원가입
# ============================================================================


async def register(db: AsyncSession, *, email: str, password: str) -> tuple[User, TokenPair]:
    # 이메일 중복 검증 — 별도 unique 제약이 있지만 명시적 에러 메시지 위해 먼저 확인
    existing = await user_repo.get_by_email(db, email)
    if existing is not None:
        raise AuthError("Email already registered", code="email_taken")

    # argon2 해시 후 사용자 생성
    user = await user_repo.create(db, email=email, password_hash=hash_password(password))

    # 회원가입 즉시 첫 family 로 로그인 처리
    family_id = uuid4()
    pair = await _issue_pair(db, user_id=user.id, family_id=family_id, parent_id=None)

    await db.commit()
    return user, pair


# ============================================================================
# 로그인
# ============================================================================


async def login(db: AsyncSession, *, email: str, password: str) -> tuple[User, TokenPair]:
    # 사용자 미존재와 비밀번호 불일치를 같은 에러로 묶어 정보 노출 최소화
    user = await user_repo.get_by_email(db, email)
    if user is None or not verify_password(password, user.password_hash):
        raise AuthError("Invalid email or password", code="invalid_credentials")

    # 매 로그인은 새 family — 디바이스/세션 격리
    family_id = uuid4()
    pair = await _issue_pair(db, user_id=user.id, family_id=family_id, parent_id=None)

    await db.commit()
    return user, pair


# ============================================================================
# 토큰 회전 (refresh)
# ============================================================================


async def refresh(db: AsyncSession, *, refresh_token: str) -> tuple[User, TokenPair]:
    # 1) JWT 서명·구조 검증
    try:
        claims = decode_refresh(refresh_token)
    except InvalidTokenError as exc:
        raise AuthError(str(exc), code="invalid_refresh") from exc

    jti = UUID(claims.jti)
    family_id = UUID(claims.fid)
    user_id = UUID(claims.sub)

    # 2) DB 에서 토큰 row 조회
    row = await refresh_token_repo.get(db, jti)
    if row is None:
        # 토큰 자체는 유효 서명이지만 DB 에 없음 → 한참 전 만료/삭제 또는 위조
        raise AuthError("Refresh token not recognized", code="invalid_refresh")

    # 3) 해시 매칭 — 같은 jti 라도 토큰 본문이 다르면 거부
    if row.token_hash != _hash_token(refresh_token):
        # 해시 불일치는 동일 jti 위조 시도 — family 폐기
        await refresh_token_repo.revoke_family(db, family_id, reason="reuse_detected")
        await db.commit()
        raise AuthError("Refresh token mismatch", code="reuse_detected")

    # 4) 재사용 감지 — 이미 revoke 된 토큰이 다시 제출되면 family 전체 폐기
    if row.revoked_at is not None:
        await refresh_token_repo.revoke_family(db, family_id, reason="reuse_detected")
        await db.commit()
        raise AuthError("Refresh token already used", code="reuse_detected")

    # 5) 만료 확인 — exp 클레임은 decode 시 검증되지만 DB 측 expires_at 도 한번 더
    if row.expires_at <= datetime.now(timezone.utc):
        raise AuthError("Refresh token expired", code="refresh_expired")

    # 6) 사용자 조회 — 응답에 user 정보를 함께 실어 프론트 부팅에 활용
    user = await user_repo.get_by_id(db, user_id)
    if user is None:
        # 토큰은 살아있지만 사용자가 사라진 비정상 상태 — family 폐기
        await refresh_token_repo.revoke_family(db, family_id, reason="manual")
        await db.commit()
        raise AuthError("User no longer exists", code="invalid_refresh")

    # 7) 회전 — 직전 토큰 revoke + 새 페어 발급 (같은 family)
    await refresh_token_repo.revoke(db, jti, reason="rotated")
    pair = await _issue_pair(db, user_id=user_id, family_id=family_id, parent_id=jti)

    await db.commit()
    return user, pair


# ============================================================================
# 로그아웃
# ============================================================================


async def logout(db: AsyncSession, *, refresh_token: str | None) -> None:
    # 쿠키가 없거나 비정상이어도 클라이언트는 정상 응답 받음 (단순 best-effort)
    if not refresh_token:
        return
    try:
        claims = decode_refresh(refresh_token)
    except InvalidTokenError:
        return

    # 해당 family 전체를 무효화 — 다중 회전 토큰이 남아있어도 한 번에 정리
    await refresh_token_repo.revoke_family(db, UUID(claims.fid), reason="logout")
    await db.commit()
