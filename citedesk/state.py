"""The inquiry status state machine (docs/BACKEND_SCHEMA.md section 5).

`ALLOWED` is every move except a retry from `failed`, which goes back to where the failed stage
started and so depends on `failure_stage`. Nothing else may change an inquiry's status.
"""

from citedesk.models import InquiryStatus as S
from citedesk.models import Stage

ALLOWED: frozenset[tuple[S, S]] = frozenset(
    {
        (S.received, S.screened),
        (S.received, S.failed),
        (S.screened, S.classified),
        (S.screened, S.archived),
        (S.screened, S.escalated),
        (S.screened, S.failed),
        (S.classified, S.routed),
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
)

# A retry from `failed` returns to the status the failed stage started from.
RETRY_TARGET: dict[Stage, S] = {
    Stage.screen: S.received,
    Stage.understand: S.screened,
    Stage.retrieve: S.routed,
    Stage.draft: S.routed,
}

# The stages that can fail from each status: exactly those whose retry returns to that status.
FAILURE_STAGES: dict[S, frozenset[Stage]] = {
    status: frozenset(stage for stage, target in RETRY_TARGET.items() if target is status)
    for status in set(RETRY_TARGET.values())
}


class InvalidTransition(Exception):
    """The requested status change is not in the state machine."""


def allowed_next(status: S, failure_stage: Stage | None = None) -> frozenset[S]:
    """Statuses reachable in one move. From `failed` this depends on the stage that failed."""
    if status is S.failed:
        target = RETRY_TARGET.get(failure_stage) if failure_stage is not None else None
        return frozenset() if target is None else frozenset({target})
    return frozenset(to for source, to in ALLOWED if source is status)


def check_transition(from_status: S, to_status: S, failure_stage: Stage | None = None) -> None:
    from_status, to_status = S(from_status), S(to_status)
    if to_status not in allowed_next(from_status, failure_stage):
        raise InvalidTransition(
            f"cannot move an inquiry from {from_status.value} to {to_status.value}"
        )
