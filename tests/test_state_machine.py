"""Pure unit tests for the status state machine (no DB, no app)."""

import pytest

from app.modules.tracker.models import ApplicationStatus as S
from app.modules.tracker.service import ALLOWED, TransitionError, validate_transition


def test_every_allowed_edge_passes() -> None:
    count = 0
    for from_status, targets in ALLOWED.items():
        for to_status in targets:
            validate_transition(from_status, to_status)
            count += 1
    assert count == 13  # guards the map against silent edits


def test_creation_allows_any_status() -> None:
    for target in S:
        validate_transition(None, target)


@pytest.mark.parametrize("state", list(S))
def test_same_status_is_illegal(state: S) -> None:
    with pytest.raises(TransitionError):
        validate_transition(state, state)


@pytest.mark.parametrize(
    ("from_status", "to_status"),
    [
        (S.SAVED, S.OA),
        (S.SAVED, S.INTERVIEW),
        (S.SAVED, S.OFFER),
        (S.SAVED, S.REJECTED),
        (S.APPLIED, S.SAVED),
        (S.APPLIED, S.OFFER),
        (S.OA, S.SAVED),
        (S.OA, S.APPLIED),
        (S.OA, S.OFFER),
        (S.INTERVIEW, S.SAVED),
        (S.INTERVIEW, S.APPLIED),
        (S.INTERVIEW, S.OA),
        (S.OFFER, S.SAVED),
        (S.OFFER, S.APPLIED),
        (S.OFFER, S.OA),
        (S.OFFER, S.INTERVIEW),
        (S.OFFER, S.OFFER),
        (S.OFFER, S.REJECTED),
    ],
)
def test_illegal_edges_raise(from_status: S, to_status: S) -> None:
    with pytest.raises(TransitionError):
        validate_transition(from_status, to_status)


@pytest.mark.parametrize("terminal", [S.REJECTED, S.WITHDRAWN])
def test_terminal_states_have_no_exits(terminal: S) -> None:
    assert ALLOWED[terminal] == set()
    for target in S:
        with pytest.raises(TransitionError):
            validate_transition(terminal, target)
