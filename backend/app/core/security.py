"""비밀번호 해싱과 JWT 인코딩/검증의 단일 진입점.

전체 흐름:
- 회원가입/로그인: argon2 로 비밀번호 해시 비교
- 토큰 발급: access(짧음, 응답 본문) + refresh(긴 수명, 쿠키)
- 토큰 검증: HS256 서명 확인 + 클레임 추출. 만료/clock skew 는 jose 가 처리

Phase 1.5 시점에서는 골격만 둔다. 실제 register/login/refresh 흐름은 Phase 2에서
auth_service.py 가 이 모듈의 함수를 조합해 사용한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from jose import JWTError, jwt

from app.core.config import settings

# argon2id 기본 파라미터 (메모리 19MB / time=2 / parallelism=1) 사용
_password_hasher = PasswordHasher()


class InvalidTokenError(Exception):
    """JWT 검증 실패. 만료/서명불일치/스키마 불일치 모두 포함."""


# ============================================================================
# 비밀번호 해시
# ============================================================================


def hash_password(plain: str) -> str:
    # argon2id 해시 (salt 자동 생성, 결과에 파라미터까지 포함됨)
    return _password_hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    # 일치 시 True, 불일치 / 손상된 해시 / 포맷 오류 모두 False 로 흡수
    try:
        return _password_hasher.verify(hashed, plain)
    except (VerifyMismatchError, InvalidHashError):
        return False


# ============================================================================
# JWT 페이로드 타입
# ============================================================================


@dataclass(frozen=True)
class AccessClaims:
    sub: str  # user id
    exp: int
    iat: int
    typ: str  # "access"


@dataclass(frozen=True)
class RefreshClaims:
    sub: str  # user id
    jti: str  # 이 refresh token 의 고유 id (DB 에 해시와 함께 저장)
    fid: str  # family id (회전 추적)
    exp: int
    iat: int
    typ: str  # "refresh"


# ============================================================================
# 토큰 인코딩
# ============================================================================


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def encode_access(user_id: str) -> str:
    # access 토큰은 짧게 — 응답 본문에 담겨 프론트 메모리로 들어감
    now = _now_utc()
    payload: dict[str, Any] = {
        "sub": user_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=settings.jwt_access_ttl_seconds)).timestamp()),
        "typ": "access",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def encode_refresh(user_id: str, *, family_id: str, jti: str | None = None) -> tuple[str, str]:
    # refresh 토큰은 회전 추적을 위해 jti + family_id 를 함께 담음
    # 반환: (jwt 문자열, jti) — 호출측이 jti 를 DB 에 저장
    now = _now_utc()
    token_jti = jti or str(uuid4())
    payload: dict[str, Any] = {
        "sub": user_id,
        "jti": token_jti,
        "fid": family_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=settings.jwt_refresh_ttl_seconds)).timestamp()),
        "typ": "refresh",
    }
    encoded = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
    return encoded, token_jti


# ============================================================================
# 토큰 디코딩
# ============================================================================


def _decode(token: str, expected_typ: str) -> dict[str, Any]:
    # 공통 디코딩: 서명/만료 검증 + typ 클레임 일치 확인
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
    except JWTError as exc:
        raise InvalidTokenError(str(exc)) from exc

    if payload.get("typ") != expected_typ:
        raise InvalidTokenError(f"unexpected typ: {payload.get('typ')}")
    if not isinstance(payload.get("sub"), str):
        raise InvalidTokenError("token missing 'sub'")
    return payload


def decode_access(token: str) -> AccessClaims:
    p = _decode(token, expected_typ="access")
    return AccessClaims(sub=p["sub"], exp=int(p["exp"]), iat=int(p["iat"]), typ="access")


def decode_refresh(token: str) -> RefreshClaims:
    p = _decode(token, expected_typ="refresh")
    jti = p.get("jti")
    fid = p.get("fid")
    if not isinstance(jti, str) or not isinstance(fid, str):
        raise InvalidTokenError("refresh token missing jti/fid")
    return RefreshClaims(
        sub=p["sub"], jti=jti, fid=fid, exp=int(p["exp"]), iat=int(p["iat"]), typ="refresh"
    )
