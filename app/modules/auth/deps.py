"""Authentication dependencies: Bearer JWT first, X-API-Key fallback."""

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.db.session import get_session
from app.modules.auth import repository, service
from app.modules.auth.models import User

bearer_scheme = HTTPBearer(auto_error=False)
API_KEY_HEADER = "X-API-Key"


async def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    """Resolve the caller to a User or raise 401 (no existence details)."""
    if credentials is not None and credentials.scheme.lower() == "bearer":
        user_id = security.decode_access_token(credentials.credentials, service.auth_secret())
        if user_id is not None:
            user = await repository.get_user_by_id(session, user_id)
            if user is not None:
                return user
    api_key = request.headers.get(API_KEY_HEADER)
    if api_key:
        user = await service.resolve_api_key(session, api_key)
        if user is not None:
            return user
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="authentication required",
    )
