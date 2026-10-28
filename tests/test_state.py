import itertools
import re
from pathlib import Path

import pytest

from citedesk import state
from citedesk.models import InquiryStatus as S
from citedesk.models import Stage

REPO_ROOT = Path(__file__).resolve().parent.parent

# Written out independently of the implementation: BACKEND_SCHEMA.md section 5, minus the retry row.
EXPECTED = {
    (S.received, S.screened),
    (S.received, S.failed),
    (S.screened, S.classified),
    (S.screened, S.archived),
    (S.screened, S.escalated),
    (S.screened, S.failed),
    (S.classified, S.routed),
    (S.classified, S.failed),
    (S.routed, S.escalated),
    (S.routed, S.archived),
    (S.routed, S.drafted),
    (S.routed, S.failed),
    (S.drafted, S.needs_review),
    (S.drafted, S.escalated),
    (S.needs_review, S.approved),
    (S.needs_review, S.rejected),
    (S.needs_review, S.escalated),
    (S.approved, S.exported),
    (S.rejected, S.drafted),
    (S.rejected, S.resolved),
    (S.escalated, S.resolved),
}

# The retry row: failed goes back to the status the failed stage started from.
RETRY = {
    Stage.screen: S.received,
    Stage.understand: S.screened,
    Stage.route: S.classified,
    Stage.retrieve: S.routed,
    Stage.draft: S.routed,
}

ALL_PAIRS = list(itertools.product(S, S))


def doc_transitions() -> set[tuple[S, S]]:
    text = (REPO_ROOT / "docs/BACKEND_SCHEMA.md").read_text("utf-8")
    section = text.split("## 5. State machine", 1)[1].split("## 6.", 1)[0]
    pairs: set[tuple[S, S]] = set()
    for line in section.splitlines():
        match = re.match(r"^\| `(\w+)` \| `(\w+)` \|", line)
        if match and match.group(1) != "failed":
            pairs.add((S(match.group(1)), S(match.group(2))))
    return pairs


# --- the table matches the document ----------------------------------------------------------


def test_the_expected_table_matches_the_schema_document() -> None:
    assert doc_transitions() == EXPECTED


def test_the_implementation_matches_the_document() -> None:
    assert state.ALLOWED == EXPECTED
    assert len(state.ALLOWED) == 21


def test_a_forbidden_shortcut_would_be_caught(monkeypatch: pytest.MonkeyPatch) -> None:
    """Known-bad check: skipping review must make the table differ from the document and the
    exhaustive pair test's expectation, not slip through silently."""
    monkeypatch.setattr(state, "ALLOWED", state.ALLOWED | {(S.received, S.approved)})
    assert doc_transitions() != state.ALLOWED
    state.check_transition(S.received, S.approved)  # the bad table now permits it...
    assert (S.received, S.approved) not in EXPECTED  # ...which the pair test would reject


def test_the_retry_table_covers_exactly_the_stages_that_can_fail() -> None:
    assert state.RETRY_TARGET == RETRY


# --- every one of the 169 pairs --------------------------------------------------------------


@pytest.mark.parametrize(("source", "target"), ALL_PAIRS, ids=[f"{a}->{b}" for a, b in ALL_PAIRS])
def test_every_status_pair(source: S, target: S) -> None:
    if (source, target) in EXPECTED:
        state.check_transition(source, target)
    else:
        with pytest.raises(state.InvalidTransition):
            state.check_transition(source, target)


def test_allowed_and_disallowed_counts_add_up() -> None:
    allowed = [p for p in ALL_PAIRS if p in EXPECTED]
    assert len(ALL_PAIRS) == 169
    assert len(allowed) == 21
    assert len(ALL_PAIRS) - len(allowed) == 148


# --- retry from failed -----------------------------------------------------------------------


@pytest.mark.parametrize("stage", list(Stage), ids=[s.value for s in Stage])
def test_failed_goes_back_only_to_where_the_failed_stage_started(stage: Stage) -> None:
    for target in S:
        if stage in RETRY and target is RETRY[stage]:
            state.check_transition(S.failed, target, failure_stage=stage)
        else:
            with pytest.raises(state.InvalidTransition):
                state.check_transition(S.failed, target, failure_stage=stage)


def test_failed_without_a_recorded_stage_cannot_move() -> None:
    for target in S:
        with pytest.raises(state.InvalidTransition):
            state.check_transition(S.failed, target, failure_stage=None)


def test_retry_targets_are_themselves_statuses_that_can_fail() -> None:
    for target in set(RETRY.values()):
        assert S.failed in state.allowed_next(target)


@pytest.mark.parametrize(
    ("source", "stages"),
    [
        (S.received, {Stage.screen}),
        (S.screened, {Stage.understand}),
        (S.classified, {Stage.route}),
        (S.routed, {Stage.retrieve, Stage.draft}),
    ],
)
def test_each_status_can_fail_only_at_its_own_stages(source: S, stages: set[Stage]) -> None:
    assert state.FAILURE_STAGES[source] == stages


def test_statuses_that_cannot_fail_have_no_failure_stages() -> None:
    for status in S:
        if S.failed not in state.allowed_next(status):
            assert status not in state.FAILURE_STAGES


# --- shape of the graph ----------------------------------------------------------------------


def test_finished_statuses_have_no_way_out() -> None:
    for status in (S.archived, S.exported, S.resolved):
        assert state.allowed_next(status) == frozenset()


def test_every_other_status_has_a_way_out() -> None:
    finished = {S.archived, S.exported, S.resolved}
    for status in S:
        if status not in finished and status is not S.failed:
            assert state.allowed_next(status), status


def test_allowed_next_for_review_is_approve_reject_or_escalate() -> None:
    assert state.allowed_next(S.needs_review) == {S.approved, S.rejected, S.escalated}


def test_every_status_is_reachable_from_received() -> None:
    reached = {S.received}
    frontier = [S.received]
    while frontier:
        current = frontier.pop()
        nexts = set(state.allowed_next(current))
        if current is S.failed:
            nexts |= set(RETRY.values())
        for nxt in nexts - reached:
            reached.add(nxt)
            frontier.append(nxt)
    assert reached == set(S)


def test_there_is_no_path_into_received_except_a_retry() -> None:
    assert all(target is not S.received for _, target in state.ALLOWED)


def test_approved_cannot_be_reached_without_going_through_review() -> None:
    assert {a for a, b in state.ALLOWED if b is S.approved} == {S.needs_review}
    assert {a for a, b in state.ALLOWED if b is S.exported} == {S.approved}
    assert {a for a, b in state.ALLOWED if b is S.needs_review} == {S.drafted}


def test_invalid_transition_message_names_both_statuses() -> None:
    with pytest.raises(state.InvalidTransition, match=r"received.*approved"):
        state.check_transition(S.received, S.approved)
