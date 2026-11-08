"""Aggregates for the Insights screen (docs/PRD.md FR-20): what came in, what was decided, how
often a draft was approved as written, and how long a review took. Counts only: no text."""

import difflib
import sqlite3
import statistics
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel

from citedesk import repo
from citedesk.models import Decision, InquiryStatus, ReasonCode, Route


class Count(BaseModel):
    code: str
    count: int


class Insights(BaseModel):
    total_inquiries: int
    by_status: list[Count]
    by_route: list[Count]
    decisions: list[Count]
    escalations_by_reason: list[Count]
    approved_unchanged_share: float | None
    edited_share: float | None
    median_review_seconds: float | None
    review_time_sample: int
    median_seconds_to_draft: float | None
    draft_time_sample: int
    # Draft quality from use (D-095): how much a reviewer changed, how often a draft was rejected,
    # and whether drafts with a warning were approved unchanged less often.
    reject_share: float | None
    median_edit_share: float | None
    edit_size_sample: int
    warned_approvals: int
    warned_unchanged: int
    clean_approvals: int
    clean_unchanged: int
    period_start: str | None
    period_end: str | None
    synthetic_data: bool


def _counts(conn: sqlite3.Connection, enum: type[StrEnum], table: str, column: str) -> list[Count]:
    """Every value of the enum, in declaration order, with zero for those never used."""
    # table and column are literals from this module, never request data
    sql = f"SELECT {column} AS code, COUNT(*) AS n FROM {table} GROUP BY {column}"  # noqa: S608
    rows = conn.execute(sql).fetchall()
    seen = {str(r["code"]): int(r["n"]) for r in rows if r["code"] is not None}
    return [Count(code=member.value, count=seen.get(member.value, 0)) for member in enum]


def _seconds_to_draft(conn: sqlite3.Connection) -> list[float]:
    """Seconds from an inquiry arriving in Citedesk to its draft first waiting for review.

    Measured from `created_at`, not `received_at`: the customer's own timestamp can be days
    older (an import) and says nothing about how long the tool took."""
    rows = conn.execute(
        "SELECT i.created_at AS arrived, MIN(a.created_at) AS ready FROM audit_events a "
        "JOIN inquiries i ON i.id = a.inquiry_id "
        "WHERE a.event_type = 'status_changed' AND a.to_status = 'needs_review' "
        "GROUP BY a.inquiry_id"
    ).fetchall()
    return [
        max(
            0.0,
            (
                datetime.fromisoformat(r["ready"]) - datetime.fromisoformat(r["arrived"])
            ).total_seconds(),
        )
        for r in rows
    ]


def changed_share(before: str, after: str) -> float:
    """The share of the draft's words a reviewer changed: 0 for none, 1 for a full rewrite.

    Words are compared in order, so spacing and line breaks alone change nothing. The texts are
    compared here and not kept."""
    old, new = before.split(), after.split()
    if not old and not new:
        return 0.0
    return 1.0 - difflib.SequenceMatcher(a=old, b=new, autojunk=False).ratio()


def _quality(conn: sqlite3.Connection) -> dict[str, Any]:
    edits: list[float] = []
    tally = {"warned_approvals": 0, "warned_unchanged": 0, "clean_approvals": 0,
             "clean_unchanged": 0}  # fmt: skip
    for row in repo.approvals_for_quality(conn):
        group = "warned" if row["warned"] else "clean"
        tally[f"{group}_approvals"] += 1
        if row["decision"] == Decision.approve:
            tally[f"{group}_unchanged"] += 1
        elif row["edited_body"] is not None:
            edits.append(changed_share(row["body"], row["edited_body"]))
    return {
        "median_edit_share": statistics.median(edits) if edits else None,
        "edit_size_sample": len(edits),
        **tally,
    }


def compute(conn: sqlite3.Connection, *, synthetic_data: bool) -> Insights:
    decisions = repo.decision_counts(conn)
    approved = decisions.get(Decision.approve, 0)
    edited = decisions.get(Decision.edit_approve, 0)
    rejected = decisions.get(Decision.reject, 0)
    judged = approved + edited + rejected
    times = repo.approval_review_seconds(conn)
    totals = conn.execute(
        "SELECT COUNT(*) AS n, MIN(created_at) AS first, MAX(created_at) AS last FROM inquiries"
    ).fetchone()
    total = int(totals["n"])
    to_draft = _seconds_to_draft(conn)
    return Insights(
        total_inquiries=total,
        by_status=_counts(conn, InquiryStatus, "inquiries", "status"),
        by_route=_counts(conn, Route, "inquiries", "route"),
        decisions=[Count(code=d.value, count=decisions.get(d, 0)) for d in Decision],
        escalations_by_reason=_counts(conn, ReasonCode, "escalations", "reason_code"),
        approved_unchanged_share=approved / (approved + edited) if approved + edited else None,
        edited_share=edited / (approved + edited) if approved + edited else None,
        median_review_seconds=statistics.median(times) if times else None,
        review_time_sample=len(times),
        median_seconds_to_draft=statistics.median(to_draft) if to_draft else None,
        draft_time_sample=len(to_draft),
        reject_share=rejected / judged if judged else None,
        **_quality(conn),
        period_start=totals["first"],
        period_end=totals["last"],
        synthetic_data=synthetic_data,
    )
