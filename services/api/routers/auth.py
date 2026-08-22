"""POST /api/v1/auth/login · /citizen/otp/* · /refresh · /logout · GET /me

Officer, state_admin, auditor and relay_node accounts are provisioned by an
administrator (data/seeds/06_app_users.sql + scripts/set_password.py), never
self-served — an open sign-up on a system that can order an evacuation would
be indefensible.

Citizens sign in with a mobile number and OTP (POST /citizen/otp/request +
/verify). That is a login, not enrollment: a recipient row must already exist
(or the seeded demo number) before a session is issued.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from pydantic import BaseModel, EmailStr, Field

from services.api.auth import (
    AuthError,
    Principal,
    authenticate,
    issue_access_token,
    issue_refresh_token,
    revoke_refresh_token,
    rotate_refresh_token,
)
from services.api.citizen_otp import request_otp, verify_otp
from services.api.deps import get_conn
from services.api.rbac import current_principal

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: EmailStr
    # Bounded to keep an oversized body from reaching bcrypt, which is
    # deliberately slow — an unbounded password field is a cheap DoS.
    password: str = Field(min_length=1, max_length=256)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    role: str
    email: str


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1, max_length=512)


class CitizenOtpRequest(BaseModel):
    phone: str = Field(min_length=8, max_length=20)


class CitizenOtpVerify(BaseModel):
    phone: str = Field(min_length=8, max_length=20)
    code: str = Field(min_length=4, max_length=8)


class MeResponse(BaseModel):
    user_id: int
    email: str
    role: str
    unit_scope_id: int | None


def _auth_failure(exc: AuthError) -> HTTPException:
    # Every credential failure returns the SAME status and code. Distinguishing
    # "no such account" from "wrong password" turns this endpoint into an
    # account-enumeration oracle.
    if exc.code == "jwt_not_configured":
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "auth_unavailable", "code": "jwt_not_configured"},
        )
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"error": "unauthenticated", "code": "invalid_credentials"},
        headers={"WWW-Authenticate": "Bearer"},
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    user_agent: str | None = Header(default=None),
    conn=Depends(get_conn),
) -> TokenResponse:
    try:
        principal = await authenticate(conn, body.email, body.password)
        access, expires_in = await issue_access_token(conn, principal)
        refresh = await issue_refresh_token(conn, principal.user_id, user_agent=user_agent)
    except AuthError as exc:
        raise _auth_failure(exc) from exc
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=expires_in,
        role=principal.role,
        email=principal.email,
    )


@router.post("/citizen/otp/request", status_code=status.HTTP_204_NO_CONTENT)
async def citizen_otp_request(body: CitizenOtpRequest, conn=Depends(get_conn)) -> Response:
    """Always 204. Missing Twilio, unknown numbers, and opted-out SIMs
    look the same so this is not an enumeration oracle."""
    try:
        await request_otp(conn, body.phone)
    except (RuntimeError, KeyError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "auth_unavailable", "code": "otp_not_configured"},
        ) from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/citizen/otp/verify", response_model=TokenResponse)
async def citizen_otp_verify(
    body: CitizenOtpVerify,
    user_agent: str | None = Header(default=None),
    conn=Depends(get_conn),
) -> TokenResponse:
    try:
        principal = await verify_otp(conn, body.phone, body.code)
        if principal.role != "citizen":
            raise AuthError()
        access, expires_in = await issue_access_token(conn, principal)
        refresh = await issue_refresh_token(conn, principal.user_id, user_agent=user_agent)
    except AuthError as exc:
        raise _auth_failure(exc) from exc
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=expires_in,
        role=principal.role,
        email=principal.email,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    body: RefreshRequest,
    user_agent: str | None = Header(default=None),
    conn=Depends(get_conn),
) -> TokenResponse:
    try:
        principal, replacement = await rotate_refresh_token(
            conn, body.refresh_token, user_agent=user_agent
        )
        access, expires_in = await issue_access_token(conn, principal)
    except AuthError as exc:
        raise _auth_failure(exc) from exc
    return TokenResponse(
        access_token=access,
        refresh_token=replacement,
        expires_in=expires_in,
        role=principal.role,
        email=principal.email,
    )


@router.post("/logout")
async def logout(body: RefreshRequest, conn=Depends(get_conn)) -> Response:
    await revoke_refresh_token(conn, body.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=MeResponse)
async def me(principal: Principal = Depends(current_principal)) -> MeResponse:
    return MeResponse(
        user_id=principal.user_id,
        email=principal.email,
        role=principal.role,
        unit_scope_id=principal.unit_scope_id,
    )
