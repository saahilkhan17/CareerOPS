"""Extractor tests: taxonomy guards, labeled-set precision/recall, edge cases."""

import json
from pathlib import Path

import pytest

from app.modules.match import extractor, taxonomy

LABELED = json.loads((Path(__file__).parent / "fixtures" / "jds" / "labeled.json").read_text())


def test_taxonomy_version_present() -> None:
    assert taxonomy.TAXONOMY_VERSION == "2026.10.1"
    assert len(taxonomy.load_taxonomy().entries) >= 70


def test_lookaround_boundaries() -> None:
    assert taxonomy.find_skills("Postgres and postgres and POSTGRES") == ["PostgreSQL"]
    found = taxonomy.find_skills("JavaScript developer")
    assert "JavaScript" in found and "Java" not in found
    found = taxonomy.find_skills("MySQL and PostgreSQL, so SQL included")
    assert {"MySQL", "PostgreSQL", "SQL"} <= set(found)
    assert "C++" in taxonomy.find_skills("C++ engineer")
    assert "C" not in taxonomy.find_skills("C++ engineer")
    assert "C" in taxonomy.find_skills("C programming language")
    assert taxonomy.canonicalize("k8s") == "Kubernetes"
    assert taxonomy.canonicalize("golang") == "Go"
    assert taxonomy.canonicalize("  ") is None
    assert taxonomy.canonicalize("not-a-skill-xyz") is None


def test_required_preferred_split() -> None:
    out = extractor.extract("Requirements: Python, Django. Nice to have: Redis.")
    assert out.required == ["Python", "Django"]
    assert out.preferred == ["Redis"]
    assert out.min_years is None
    assert out.seniority.level == "unspecified"


def test_both_sections_means_required() -> None:
    out = extractor.extract("Requirements: Docker.\nNice to have: Docker is a plus.")
    assert out.required == ["Docker"]
    assert out.preferred == []


def test_min_years_and_seniority() -> None:
    out = extractor.extract("Senior backend. 5+ years of experience with Python.")
    assert out.min_years == 5
    assert out.seniority.level == "senior"
    assert out.seniority.senior_hits == ["senior"]


def test_mixed_seniority() -> None:
    out = extractor.extract("Senior engineer hiring junior developers. Python.")
    assert out.seniority.level == "mixed"
    assert out.seniority.junior_hits == ["junior"]
    assert out.seniority.senior_hits == ["senior"]


def test_labeled_set_precision_recall() -> None:
    assert len(LABELED) >= 20
    tp = fp = fn = 0
    split_errors: list[str] = []
    for doc in LABELED:
        out = extractor.extract(doc["text"])
        expected = set(doc["expected_skills"])
        got = set(out.skills)
        tp += len(expected & got)
        fp += len(got - expected)
        fn += len(expected - got)
        if set(out.required) != set(doc["expected_required"]):
            split_errors.append(
                f"{doc['id']} required: got {sorted(out.required)} "
                f"want {sorted(doc['expected_required'])}"
            )
        if set(out.preferred) != set(doc["expected_preferred"]):
            split_errors.append(
                f"{doc['id']} preferred: got {sorted(out.preferred)} "
                f"want {sorted(doc['expected_preferred'])}"
            )
        assert out.min_years == doc["min_years"], f"{doc['id']} min_years"
        assert out.seniority.level == doc["seniority"], f"{doc['id']} seniority"
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    print(f"\nextraction P/R over {len(LABELED)} JDs: P={precision:.3f} R={recall:.3f}")
    assert not split_errors, "\n".join(split_errors)
    assert precision >= 0.7, f"precision {precision:.3f}"
    assert recall >= 0.7, f"recall {recall:.3f}"


def test_empty_raises() -> None:
    with pytest.raises(ValueError):
        extractor.extract("")
    with pytest.raises(ValueError):
        extractor.extract("   \n  ")


def test_huge_input_truncated() -> None:
    out = extractor.extract(("Python. " * 30000)[:200000])
    assert "Python" in out.skills


def test_non_english_does_not_crash() -> None:
    out = extractor.extract("Nous recherchons un développeur Python avec Docker.")
    assert "Python" in out.skills and "Docker" in out.skills
