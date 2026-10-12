"""Auth request/response schemas (Pydantic v2, never ORM objects)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)


class RefreshIn(BaseModel):
    refresh_token: str = Field(min_length=20)


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    created_at: datetime


class ApiKeyCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class ApiKeyOut(BaseModel):
    """Returned once at creation — the plaintext key never leaves this response."""

    id: uuid.UUID
    name: str
    key: str
    created_at: datetime


class ApiKeyListOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    last_used_at: datetime | None
    created_at: datetime
