"""Auth endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response

from app.config import get_settings
from app.deps import DB, Client
from app.schemas.auth import (
    ForgotPasswordIn,
    LoginIn,
    RegisterIn,
    RegisterOut,
    ResendVerificationIn,
    ResetPasswordIn,
    TokenOut,
    VerifyEmailIn,
)
from app.schemas.common import OkOut
from app.services import auth_service, email_service, rate_limit

router = APIRouter(prefix="/auth", tags=["auth"])
REFRESH_COOKIE = "advar_refresh"


def _set_refresh_cookie(response: Response, token: str) -> None:
    s = get_settings()
    response.set_cookie(
        REFRESH_COOKIE,
        token,
        max_age=s.JWT_REFRESH_TTL_DAYS * 24 * 3600,
        httponly=True,
        secure=s.COOKIE_SECURE,
        samesite="lax",
        domain=s.COOKIE_DOMAIN or None,
        path=f"{s.API_PREFIX}/auth",
    )


def _clear_refresh_cookie(response: Response) -> None:
    s = get_settings()
    response.delete_cookie(REFRESH_COOKIE, domain=s.COOKIE_DOMAIN or None, path=f"{s.API_PREFIX}/auth")


def _token_out(user, access: str) -> TokenOut:  # noqa: ANN001
    return TokenOut(
        access_token=access,
        expires_in=get_settings().JWT_ACCESS_TTL_MIN * 60,
        user_id=user.id,
        role=user.role,
    )


@router.post("/register", response_model=RegisterOut, status_code=201)
async def register(body: RegisterIn, db: DB, client: Client) -> RegisterOut:
    await rate_limit.enforce(rate_limit.REGISTER, client.ip or "unknown")
    user, token = await auth_service.register(
        db, email=body.email, password=body.password, name=body.name, country=body.country, locale=body.locale
    )
    await db.commit()
    await email_service.send_verification(user.email, token)
    return RegisterOut(
        user_id=user.id, email=user.email, message="Check your e-mail for the verification link"
    )


@router.post("/verify-email", response_model=OkOut)
async def verify_email(body: VerifyEmailIn, db: DB) -> OkOut:
    await auth_service.verify_email(db, body.token)
    return OkOut(message="E-mail verified")


@router.post("/resend-verification", response_model=OkOut)
async def resend_verification(body: ResendVerificationIn, db: DB, client: Client) -> OkOut:
    await rate_limit.enforce(rate_limit.RESEND, client.ip or "unknown")
    token = await auth_service.resend_verification(db, body.email)
    await db.commit()
    if token:
        await email_service.send_verification(body.email, token)
    return OkOut(message="If the account exists and is not verified, a new link was sent")


@router.post("/login", response_model=TokenOut)
async def login(body: LoginIn, db: DB, client: Client, response: Response) -> TokenOut:
    await rate_limit.enforce(rate_limit.LOGIN, client.ip or "unknown")
    user, access, refresh = await auth_service.login(
        db, email=body.email, password=body.password, user_agent=client.user_agent, ip=client.ip
    )
    _set_refresh_cookie(response, refresh)
    return _token_out(user, access)


@router.post("/refresh", response_model=TokenOut)
async def refresh(request: Request, db: DB, client: Client, response: Response) -> TokenOut:
    token = request.cookies.get(REFRESH_COOKIE) or request.headers.get("x-refresh-token") or ""
    user, access, new_refresh = await auth_service.refresh(db, token, client.user_agent, client.ip)
    _set_refresh_cookie(response, new_refresh)
    return _token_out(user, access)


@router.post("/logout", response_model=OkOut)
async def logout(request: Request, db: DB, response: Response) -> OkOut:
    token = request.cookies.get(REFRESH_COOKIE) or request.headers.get("x-refresh-token")
    await auth_service.logout(db, token)
    _clear_refresh_cookie(response)
    return OkOut(message="Logged out")


@router.post("/forgot-password", response_model=OkOut)
async def forgot_password(body: ForgotPasswordIn, db: DB, client: Client) -> OkOut:
    await rate_limit.enforce(rate_limit.FORGOT, client.ip or "unknown")
    token = await auth_service.forgot_password(db, body.email)
    await db.commit()
    if token:
        await email_service.send_password_reset(body.email, token)
    return OkOut(message="If the account exists, a reset link was sent")


@router.post("/reset-password", response_model=OkOut)
async def reset_password(body: ResetPasswordIn, db: DB) -> OkOut:
    await auth_service.reset_password(db, body.token, body.password)
    return OkOut(message="Password updated; log in again")
