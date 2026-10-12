"""Match request/response schemas (Pydantic v2, never ORM objects)."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ProfileSkill(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    years: float | None = Field(default=None, ge=0, le=60)


class ProfileIn(BaseModel):
    skills: list[ProfileSkill] = Field(default_factory=list, max_length=200)
    target_roles: list[str] = Field(default_factory=list, max_length=20)
    education: str | None = None
    preferences: dict[str, Any] = Field(default_factory=dict)


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    skills: list[ProfileSkill]
    target_roles: list[str]
    education: str | None
    preferences: dict[str, Any]
    updated_at: datetime


class MatchRequest(BaseModel):
    title: str | None = Field(default=None, max_length=320)
    text: str = Field(min_length=1, max_length=200_000)


class ComponentBreakdown(BaseModel):
    score: int
    weight: float
    matched: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)


class MatchResponse(BaseModel):
    id: uuid.UUID
    score: int = Field(ge=0, le=100)
    breakdown: dict[str, Any]
    matched_skills: list[str]
    missing_skills: list[str]
    suggestions: list[str]
    llm_explanation: str | None
    created_at: datetime


class MatchHistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    application_id: uuid.UUID | None
    title: str | None
    score: int
    created_at: datetime
