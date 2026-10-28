"""Aggregates for the Insights screen (docs/PRD.md FR-20): what came in, what was decided, how
often a draft was approved as written, and how long a review took. Counts only: no text."""

import sqlite3
import statistics
from enum import StrEnum

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
    synthetic_data: bool


def _counts(conn: sqlite3.Connection, enum: type[StrEnum], table: str, column: str) -> list[Count]:
    """Every value of the enum, in declaration order, with zero for those never used."""
    # table and column are literals from this module, never request data
    sql = f"SELECT {column} AS code, COUNT(*) AS n FROM {table} GROUP BY {column}"  # noqa: S608
    rows = conn.execute(sql).fetchall()
    seen = {str(r["code"]): int(r["n"]) for r in rows if r["code"] is not None}
    return [Count(code=member.value, count=seen.get(member.value, 0)) for member in enum]


def compute(conn: sqlite3.Connection, *, synthetic_data: bool) -> Insights:
    decisions = repo.decision_counts(conn)
    approved = decisions.get(Decision.approve, 0)
    edited = decisions.get(Decision.edit_approve, 0)
    times = repo.approval_review_seconds(conn)
    total = int(conn.execute("SELECT COUNT(*) AS n FROM inquiries").fetchone()["n"])
    return Insights(
        total_inquiries=total,
        by_status=_counts(conn, InquiryStatus, "inquiries", "status"),
        by_route=_counts(conn, Route, "inquiries", "route"),
        decisions=[Count(code=d.value, count=decisions.get(d, 0)) for d in Decision],
        escalations_by_reason=_counts(conn, ReasonCode, "escalations", "reason_code"),
        approved_unchanged_share=approved / (approved + edited) if approved + edited else None,
        edited_share=edited / (approved + edited) if approved + edited else None,
        median_review_seconds=statistics.median(times) if times else None,
        synthetic_data=synthetic_data,
    )
