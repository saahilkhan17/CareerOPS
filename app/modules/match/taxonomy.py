"""Versioned skill taxonomy: canonical names + aliases, deterministic matching."""

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

DATA_PATH = Path(__file__).parent / "data" / "skills.json"


@dataclass(frozen=True)
class SkillEntry:
    canonical: str
    aliases: tuple[str, ...]
    case_sensitive: bool
    pattern: re.Pattern[str]


def _compile(entry: dict[str, Any]) -> SkillEntry:
    canonical = str(entry["canonical"])
    aliases = tuple(str(a) for a in entry.get("aliases", []))
    sensitive = bool(entry.get("sensitive", False))
    not_after = "".join(str(c) for c in entry.get("not_after", []))
    # Longest alias first so "django rest framework" wins over "django".
    variants = sorted([canonical, *aliases], key=len, reverse=True)
    alternation = "|".join(re.escape(v) for v in variants)
    flags = 0 if sensitive else re.IGNORECASE
    # Trailing guard: no word char and none of the not_after chars (e.g. C
    # must not match inside C++/C#, R must not match inside R&D).
    trailing = "(?![\\w" + "".join(re.escape(c) for c in not_after) + "])"
    pattern = re.compile(rf"(?<!\w)(?:{alternation}){trailing}", flags)
    return SkillEntry(canonical, aliases, sensitive, pattern)


@dataclass(frozen=True)
class Taxonomy:
    version: str
    entries: tuple[SkillEntry, ...]


@lru_cache
def load_taxonomy() -> Taxonomy:
    """Load (and cache) the taxonomy from skills.json."""
    raw = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    entries = tuple(_compile(e) for e in raw["skills"])
    return Taxonomy(version=str(raw["version"]), entries=entries)


TAXONOMY_VERSION = load_taxonomy().version


def canonicalize(name: str) -> str | None:
    """Map a raw skill name to its canonical form, else None."""
    cleaned = name.strip()
    if not cleaned:
        return None
    for entry in load_taxonomy().entries:
        if entry.case_sensitive:
            if cleaned == entry.canonical or cleaned in entry.aliases:
                return entry.canonical
        elif cleaned.lower() == entry.canonical.lower() or cleaned.lower() in (
            a.lower() for a in entry.aliases
        ):
            return entry.canonical
    return None


def find_skills(text: str) -> list[str]:
    """Return canonical skills found in text, in first-seen order, deduped."""
    hits: list[tuple[int, str]] = []
    for entry in load_taxonomy().entries:
        for match in entry.pattern.finditer(text):
            hits.append((match.start(), entry.canonical))
            break  # one hit per skill is enough for presence
    hits.sort(key=lambda h: h[0])
    seen: set[str] = set()
    ordered: list[str] = []
    for _, canonical in hits:
        if canonical not in seen:
            seen.add(canonical)
            ordered.append(canonical)
    return ordered
