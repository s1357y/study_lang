"""인증 라우트 — /register, /login, /refresh, /logout, /me.

라우터의 책임:
- 요청 본문 검증 (Pydantic)
- auth_service 호출
- access 는 응답 본문, refresh 는 HttpOnly 쿠키로 분리
- 도메인 에러(AuthError)를 HTTP 응답으로 매핑
"""

from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import current_user, get_db
from app.api.v1.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserPublic,
)
from app.core.config import settings
from app.models.user import User
from app.services import auth_service
from app.services.auth_service import AuthError, TokenPair

router = APIRouter()


# ============================================================================
# 쿠키 / 응답 헬퍼
# ============================================================================


def _set_refresh_cookie(response: Response, pair: TokenPair) -> None:
    # refresh 토큰은 HttpOnly + 경로 제한으로 다른 엔드포인트에 노출되지 않게 한다
    response.set_cookie(
        key="refresh_token",
        value=pair.refresh_token,
        max_age=pair.refresh_expires_in,
        httponly=True,
        secure=settings.refresh_cookie_secure,
        samesite="lax",
        path=settings.refresh_cookie_path,
        domain=settings.refresh_cookie_domain or None,
    )


def _clear_refresh_cookie(response: Response) -> None:
    # 같은 path/domain 으로 만료 쿠키를 내려 브라우저가 삭제하게 함
    response.delete_cookie(
        key="refresh_token",
        path=settings.refresh_cookie_path,
        domain=settings.refresh_cookie_domain or None,
    )


def _to_token_response(user: User, pair: TokenPair) -> TokenResponse:
    return TokenResponse(
        access_token=pair.access_token,
        expires_in=pair.access_expires_in,
        user=UserPublic.model_validate(user),
    )


def _auth_error_to_http(exc: AuthError) -> HTTPException:
    # 도메인 코드 → HTTP 상태 매핑. 정보 노출 최소화를 위해 기본은 401.
    if exc.code == "email_taken":
        return HTTPException(status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(status.HTTP_401_UNAUTHORIZED, detail=str(exc))


# ============================================================================
# 라우트
# ============================================================================


@router.post("/register", response_model=TokenResponse)
async def register(
    body: RegisterRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    # 회원가입 → 즉시 첫 토큰 페어 발급 (자동 로그인)
    try:
        user, pair = await auth_service.register(
            db, email=body.email, password=body.password
        )
    except AuthError as exc:
        raise _auth_error_to_http(exc) from exc
    _set_refresh_cookie(response, pair)
    return _to_token_response(user, pair)


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    try:
        user, pair = await auth_service.login(
            db, email=body.email, password=body.password
        )
    except AuthError as exc:
        raise _auth_error_to_http(exc) from exc
    _set_refresh_cookie(response, pair)
    return _to_token_response(user, pair)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    # 쿠키 부재면 정상 흐름 아님 — 즉시 401
    if not refresh_token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Missing refresh token")

    try:
        user, pair = await auth_service.refresh(db, refresh_token=refresh_token)
    except AuthError as exc:
        # 재사용 감지 등 — 쿠키도 함께 정리해 클라이언트가 다시 로그인하게 유도
        _clear_refresh_cookie(response)
        raise _auth_error_to_http(exc) from exc

    # 회전된 새 refresh 를 쿠키에 덮어쓰기
    _set_refresh_cookie(response, pair)
    return _to_token_response(user, pair)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
) -> None:
    # 쿠키가 있으면 family 전체 폐기. 없어도 클라이언트 측 정리를 위해 204 응답.
    await auth_service.logout(db, refresh_token=refresh_token)
    _clear_refresh_cookie(response)


@router.get("/me", response_model=UserPublic)
async def me(user: User = Depends(current_user)) -> UserPublic:
    # access 토큰이 유효하면 현재 사용자 정보 반환
    return UserPublic.model_validate(user)
