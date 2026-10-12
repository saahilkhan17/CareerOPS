"""Seed demo data for local review: demo user, apps, listings, matches.

Requires the schema first (`make migrate`). Safe to rerun: exits cleanly
when the demo user already exists.

Usage: python scripts/seed.py  (or `make seed`)
"""

import asyncio
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core import security  # noqa: E402
from app.core.time import utcnow  # noqa: E402
from app.db.session import get_session_factory  # noqa: E402
from app.modules.auth import repository as auth_repo  # noqa: E402
from app.modules.ingestion import service as ingestion_service  # noqa: E402
from app.modules.ingestion.sources import RawListing  # noqa: E402
from app.modules.match import repository as match_repo  # noqa: E402
from app.modules.match import service as match_service  # noqa: E402
from app.modules.tracker import repository as tracker_repo  # noqa: E402
from app.modules.tracker import service as tracker_service  # noqa: E402
from app.modules.tracker.models import ApplicationStatus  # noqa: E402
from app.modules.tracker.schemas import ApplicationCreate  # noqa: E402

DEMO_EMAIL = "demo@careerops.dev"
DEMO_PASSWORD = "demo1234"

APPLICATIONS: list[tuple[str, str, list[ApplicationStatus]]] = [
    ("Acme", "Backend Engineer", []),
    ("Globex", "Senior Backend Engineer", [ApplicationStatus.APPLIED]),
    ("Initech", "Python Developer", [ApplicationStatus.APPLIED, ApplicationStatus.OA]),
    (
        "Umbrella",
        "Backend Engineer",
        [ApplicationStatus.APPLIED, ApplicationStatus.INTERVIEW],
    ),
    (
        "Hooli",
        "Staff Backend Engineer",
        [ApplicationStatus.APPLIED, ApplicationStatus.INTERVIEW, ApplicationStatus.OFFER],
    ),
    ("Stark", "DevOps Engineer", [ApplicationStatus.APPLIED, ApplicationStatus.REJECTED]),
    ("Wayne", "Frontend Engineer", [ApplicationStatus.WITHDRAWN]),
    (
        "Massive",
        "Data Engineer",
        [ApplicationStatus.APPLIED, ApplicationStatus.OA, ApplicationStatus.INTERVIEW],
    ),
]

LISTINGS: list[tuple[str, str, str, str]] = [
    # (external_id, title, company, description)
    (
        "demo-01",
        "Backend Engineer (Python)",
        "Acme",
        "Python and FastAPI required. PostgreSQL. 3 years of experience. "
        "Nice to have: Docker and AWS.",
    ),
    (
        "demo-02",
        "Senior Django Developer",
        "Globex",
        "Senior developer needed. 5+ years with Python and Django. "
        "PostgreSQL and Redis. Nice to have: React.",
    ),
    (
        "demo-03",
        "Frontend Developer",
        "Wayne",
        "React, TypeScript and CSS required. 2 years of experience. Nice to have: Figma.",
    ),
    (
        "demo-04",
        "DevOps Engineer",
        "Stark",
        "AWS, Kubernetes and Terraform required. 4 years of experience. Nice to have: Prometheus.",
    ),
    (
        "demo-05",
        "Data Engineer",
        "Massive",
        "Python, SQL and Airflow required. Snowflake. Nice to have: dbt.",
    ),
    (
        "demo-06",
        "Machine Learning Engineer",
        "Hooli",
        "Python and PyTorch required. Machine learning fundamentals. Nice to have: AWS.",
    ),
    (
        "demo-07",
        "Backend Engineer (Go)",
        "Initech",
        "Go and gRPC required. Docker and Kubernetes. Nice to have: PostgreSQL.",
    ),
    (
        "demo-08",
        "QA Automation Engineer",
        "Umbrella",
        "Selenium and Pytest required. CI/CD pipelines. Nice to have: Playwright.",
    ),
    (
        "demo-09",
        "Platform Lead",
        "Hooli",
        "Lead role. 6 years with AWS, Terraform and Kubernetes. "
        "Prometheus monitoring. Nice to have: Go.",
    ),
    (
        "demo-10",
        "Junior Backend Developer",
        "Acme",
        "Fresher welcome. Python and SQL fundamentals. Git. Nice to have: Django.",
    ),
    (
        "demo-11",
        "Fullstack Developer",
        "Globex",
        "React and Node.js required. PostgreSQL. Nice to have: TypeScript and Docker.",
    ),
    (
        "demo-12",
        "Backend Engineer (Java)",
        "Massive",
        "Java and Spring Boot required. MySQL. 4 years of experience. Nice to have: Kafka.",
    ),
]

JD_BACKEND = """Backend Engineer.

Requirements:
- 3 years of experience with Python and FastAPI.
- PostgreSQL.

Nice to have:
- Docker and AWS.
"""


async def main() -> None:
    factory = get_session_factory()
    async with factory() as session:
        # Schema present?
        try:
            existing = await auth_repo.get_user_by_email(session, DEMO_EMAIL)
        except Exception:
            print("Schema not found. Run `make migrate` first, then `make seed`.")
            return
        if existing is not None:
            print(f"Demo user {DEMO_EMAIL} already exists. Nothing to do.")
            return

        user = await auth_repo.create_user(
            session, DEMO_EMAIL, security.hash_password(DEMO_PASSWORD)
        )
        await session.commit()
        print(f"user: {DEMO_EMAIL}")

        await match_repo.upsert_profile(
            session,
            user.id,
            [
                {"name": "Python", "years": 4},
                {"name": "FastAPI", "years": 3},
                {"name": "PostgreSQL", "years": 4},
                {"name": "Docker", "years": 2},
            ],
            ["Backend Engineer"],
            "B.Tech Computer Science",
            {"remote": True},
        )
        await session.commit()
        print("profile: 4 skills, 1 target role")

        apps = []
        for company, title, walk in APPLICATIONS:
            row = await tracker_service.create_application(
                session, user, ApplicationCreate(company=company, title=title)
            )
            for target in walk:
                row = await tracker_service.change_status(session, user, row.id, target)
            apps.append(row)
        print(f"applications: {len(apps)} (saved→offer spread)")

        await tracker_repo.add_note(
            session, apps[1].id, "Referral from Priya — team hires monthly."
        )
        await tracker_repo.add_note(session, apps[4].id, "Offer call Thursday. Ask about on-call.")
        await session.commit()
        await tracker_repo.add_reminder(session, apps[3].id, utcnow() - timedelta(days=1))
        await tracker_repo.add_reminder(session, apps[4].id, utcnow() + timedelta(days=3))
        await session.commit()
        print("notes: 2, reminders: 2 (1 overdue)")

    async def _fetch() -> list[RawListing]:
        return [
            RawListing(
                source="seed-demo",
                external_id=eid,
                title=title,
                company=company,
                description=desc,
                remote="Remote" in desc,
            )
            for eid, title, company, desc in LISTINGS
        ]

    stats = await ingestion_service.run_ingestion("seed-demo", factory, fetcher=_fetch)
    print(f"listings: inserted={stats['inserted']} skipped={stats['skipped']}")

    async with factory() as session:
        user = await auth_repo.get_user_by_email(session, DEMO_EMAIL)
        assert user is not None
        await match_service.run_match(session, user, "Backend Engineer", JD_BACKEND)
        await match_service.run_match(
            session,
            user,
            "Senior Django Developer",
            "Senior developer. Requirements: 5 years of Python and Django. PostgreSQL.",
        )
        print("match results: 2")

    from app.modules.analytics import service as analytics_service

    refreshed = await analytics_service.refresh_summary(factory)
    print(f"summary rows: {refreshed}")

    print()
    print("Done. Log in with:")
    print(f"  email:    {DEMO_EMAIL}")
    print(f"  password: {DEMO_PASSWORD}")


if __name__ == "__main__":
    asyncio.run(main())
