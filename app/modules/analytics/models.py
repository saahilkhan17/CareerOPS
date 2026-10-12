"""Analytics models: precomputed daily skill counts (summary table)."""

from datetime import date

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SkillDailyCount(Base):
    """Postings per skill per day — rebuilt by the refresh task."""

    __tablename__ = "skill_daily_counts"

    day: Mapped[date] = mapped_column(primary_key=True)
    skill: Mapped[str] = mapped_column(String(120), primary_key=True)
    postings: Mapped[int] = mapped_column(Integer)
