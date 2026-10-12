"""Deterministic JD extraction: skills, required/preferred, YoE, seniority."""

import re
from dataclasses import dataclass, field

from app.modules.match.taxonomy import find_skills

MAX_TEXT_CHARS = 50_000
MAX_YEARS = 20

PREFERRED_CUES = (
    "nice to have",
    "nice-to-have",
    "preferred",
    "bonus",
    "good to have",
    "desired",
    "a plus",
    "pluses",
)
REQUIRED_CUES = (
    "must have",
    "must-have",
    "required",
    "requirements",
    "qualifications",
    "what you'll need",
    "what you need",
    "minimum",
    "essential",
    "mandatory",
    "responsibilities",
)

YEARS_RE = re.compile(r"(\d{1,2})\s*(?:-\s*\d{1,2}\s*)?\+?\s*(?:years?|yrs?)\b", re.IGNORECASE)

JUNIOR_CUES = (
    "junior",
    "jr.",
    "entry-level",
    "entry level",
    "fresher",
    "graduate",
    "intern",
)
SENIOR_CUES = (
    "senior",
    "sr.",
    "lead",
    "staff",
    "principal",
    "architect",
)


@dataclass
class Seniority:
    level: str  # junior | senior | mixed | unspecified
    junior_hits: list[str] = field(default_factory=list)
    senior_hits: list[str] = field(default_factory=list)


@dataclass
class ExtractedJD:
    skills: list[str]
    required: list[str]
    preferred: list[str]
    min_years: int | None
    seniority: Seniority


def _section_of(line: str) -> str | None:
    """Return 'preferred'/'required' when the line looks like a section header."""
    cleaned = line.strip().lower().rstrip(":")
    if len(cleaned) > 60:
        return None
    if any(cue in cleaned for cue in PREFERRED_CUES):
        return "preferred"
    if any(cue in cleaned for cue in REQUIRED_CUES):
        return "required"
    return None


def _sentence_section(sentence: str, current: str) -> str:
    """Per-sentence override: explicit cues beat the ambient section."""
    lowered = sentence.lower()
    if any(cue in lowered for cue in PREFERRED_CUES):
        return "preferred"
    if any(cue in lowered for cue in REQUIRED_CUES):
        return "required"
    return current


def _split_sentences(line: str) -> list[str]:
    parts = re.split(r"(?<=[.!?;\n])\s+|\s*[•\-*]\s+", line)
    return [p.strip() for p in parts if p.strip()]


def _min_years(text: str) -> int | None:
    numbers = [int(n) for n in YEARS_RE.findall(text)]
    if not numbers:
        return None
    return min(max(numbers), MAX_YEARS)


def _seniority(text: str) -> Seniority:
    lowered = text.lower()
    junior = sorted({c for c in JUNIOR_CUES if c in lowered})
    senior = sorted({c for c in SENIOR_CUES if c in lowered})
    if junior and senior:
        level = "mixed"
    elif senior:
        level = "senior"
    elif junior:
        level = "junior"
    else:
        level = "unspecified"
    return Seniority(level=level, junior_hits=junior, senior_hits=senior)


def extract(text: str) -> ExtractedJD:
    """Extract structured signals from raw JD text (deterministic, pure)."""
    if not text or not text.strip():
        raise ValueError("JD text is empty")
    text = text[:MAX_TEXT_CHARS]

    required: list[str] = []
    preferred: list[str] = []
    section = "required"
    for line in text.splitlines():
        header = _section_of(line)
        if header is not None:
            section = header
        for sentence in _split_sentences(line):
            bucket = _sentence_section(sentence, section)
            for skill in find_skills(sentence):
                target = preferred if bucket == "preferred" else required
                if skill not in target:
                    target.append(skill)

    # A skill claimed in both sections counts as required.
    preferred = [s for s in preferred if s not in required]
    skills = [*required, *[s for s in preferred if s not in required]]
    return ExtractedJD(
        skills=skills,
        required=required,
        preferred=preferred,
        min_years=_min_years(text),
        seniority=_seniority(text),
    )
