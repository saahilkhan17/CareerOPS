"""Analytics response schemas."""

from pydantic import BaseModel, Field


class SkillCount(BaseModel):
    skill: str
    postings: int


class CoocOut(BaseModel):
    items: list[SkillCount]


class SalaryStats(BaseModel):
    count: int
    min: int | None
    median: int | None
    p75: int | None


class TrendPoint(BaseModel):
    bucket: str
    postings: int


class GapSkill(BaseModel):
    skill: str
    postings: int


class SkillsTopOut(BaseModel):
    items: list[SkillCount]
    total_skills: int = Field(description="Distinct skills counted (pre-limit)")


class SalaryOut(BaseModel):
    stats: SalaryStats


class TrendsOut(BaseModel):
    granularity: str
    points: list[TrendPoint]


class GapsOut(BaseModel):
    items: list[GapSkill]
