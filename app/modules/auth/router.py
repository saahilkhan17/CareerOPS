"""Auth routes: register, login, refresh, logout, me, API keys."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.auth import service
from app.modules.auth.deps import get_current_user
from app.modules.auth.models import User
from app.modules.auth.schemas import (
    ApiKeyCreateIn,
    ApiKeyListOut,
    ApiKeyOut,
    LoginIn,
    RefreshIn,
    RegisterIn,
    TokenOut,
    UserOut,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterIn,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    """Create an account."""
    try:
        return await service.register(session, payload.email, payload.password)
    except service.EmailTakenError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="email already registered"
        ) from None


@router.post("/login", response_model=TokenOut)
async def login(
    payload: LoginIn,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TokenOut:
    """Exchange credentials for an access + refresh token pair."""
    user = await service.authenticate(session, payload.email, payload.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")
    access, refresh = await service.issue_token_pair(session, user)
    return TokenOut(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=TokenOut)
async def refresh(
    payload: RefreshIn,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TokenOut:
    """Rotate a refresh token into a fresh pair; the old one dies."""
    rotated = await service.rotate_refresh(session, payload.refresh_token)
    if rotated is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or expired refresh token",
        )
    _, access, new_refresh = rotated
    return TokenOut(access_token=access, refresh_token=new_refresh)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    payload: RefreshIn,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    """Revoke a refresh token (idempotent)."""
    await service.logout(session, payload.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserOut)
async def me(user: Annotated[User, Depends(get_current_user)]) -> User:
    """Return the authenticated user."""
    return user


@router.post("/api-keys", response_model=ApiKeyOut, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    payload: ApiKeyCreateIn,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ApiKeyOut:
    """Create an API key; the plaintext value is shown exactly once."""
    row, key = await service.create_api_key(session, user, payload.name)
    return ApiKeyOut(id=row.id, name=row.name, key=key, created_at=row.created_at)


@router.get("/api-keys", response_model=list[ApiKeyListOut])
async def list_api_keys(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[ApiKeyListOut]:
    """List active API keys (hashes and plaintext never exposed)."""
    rows = await service.list_api_keys(session, user)
    return [ApiKeyListOut.model_validate(r) for r in rows]


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_key(
    key_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    """Revoke an API key."""
    ok = await service.revoke_api_key(session, user, key_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="api key not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
