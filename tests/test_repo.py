import sqlite3
from typing import Any

import pytest

from citedesk import repo
from citedesk.db import connect, migrate
from citedesk.models import (
    CheckCode,
    Claim,
    ClassifiedIntent,
    Confidence,
    Decision,
    DraftKind,
    DraftStatus,
    EscalationSource,
    ExportMethod,
    ExtractedFields,
    InquiryStatus,
    Intent,
    ReasonCode,
    Route,
    ScreeningResult,
    Sentiment,
    Source,
    Urgency,
)

T1 = "2026-10-28T10:00:00Z"
T2 = "2026-10-28T11:00:00Z"
T3 = "2026-10-28T12:00:00Z"


@pytest.fixture
def conn() -> sqlite3.Connection:
    c = connect(":memory:")
    migrate(c)
    return c


def new_inquiry(conn: sqlite3.Connection, **over: Any) -> int:
    args: dict[str, Any] = {"channel": "web_form", "body": "How much for a drain?", "now": T1}
    return repo.insert_inquiry(conn, **{**args, **over})


def set_status(conn: sqlite3.Connection, inquiry_id: int, status: str) -> None:
    # The state machine (Task 4) is the only supported way; tests set it directly.
    conn.execute("UPDATE inquiries SET status = ? WHERE id = ?", (status, inquiry_id))


def new_draft(conn: sqlite3.Connection, inquiry_id: int, **over: Any) -> int:
    args: dict[str, Any] = {
        "inquiry_id": inquiry_id,
        "kind": DraftKind.reply,
        "body": "Hello",
        "model": "m",
        "prompt_version": "draft-v1",
        "now": T1,
    }
    return repo.insert_draft(conn, **{**args, **over})


# --- inquiries -------------------------------------------------------------------------------


def test_insert_and_get_an_inquiry(conn: sqlite3.Connection) -> None:
    inquiry_id = new_inquiry(conn, sender_name="Alex Rivera", subject="drain")
    inquiry = repo.get_inquiry(conn, inquiry_id)
    assert inquiry is not None
    assert inquiry.status is InquiryStatus.received
    assert inquiry.is_synthetic is True
    assert (inquiry.created_at, inquiry.updated_at, inquiry.received_at) == (T1, T1, T1)
    assert (inquiry.sender_name, inquiry.subject) == ("Alex Rivera", "drain")


def test_received_at_can_differ_from_creation_time(conn: sqlite3.Connection) -> None:
    inquiry = repo.get_inquiry(conn, new_inquiry(conn, received_at="2026-10-27T09:00:00Z"))
    assert inquiry is not None
    assert inquiry.received_at == "2026-10-27T09:00:00Z"
    assert inquiry.created_at == T1


def test_get_returns_none_for_an_unknown_id(conn: sqlite3.Connection) -> None:
    assert repo.get_inquiry(conn, 999) is None


def test_external_id_must_be_unique_per_channel(conn: sqlite3.Connection) -> None:
    new_inquiry(conn, external_id="a-1")
    new_inquiry(conn, external_id="a-1", channel="email")
    with pytest.raises(sqlite3.IntegrityError):
        new_inquiry(conn, external_id="a-1")


def test_find_by_external_id(conn: sqlite3.Connection) -> None:
    inquiry_id = new_inquiry(conn, external_id="a-1")
    found = repo.find_by_external_id(conn, "web_form", "a-1")
    assert found is not None and found.id == inquiry_id
    assert repo.find_by_external_id(conn, "email", "a-1") is None


def test_update_changes_allowed_fields_and_bumps_updated_at(conn: sqlite3.Connection) -> None:
    inquiry_id = new_inquiry(conn)
    repo.update_inquiry(
        conn,
        inquiry_id,
        route=Route.escalate,
        urgency=Urgency.urgent,
        primary_intent=Intent.health_or_safety,
        now=T2,
    )
    inquiry = repo.get_inquiry(conn, inquiry_id)
    assert inquiry is not None
    assert (inquiry.route, inquiry.urgency, inquiry.primary_intent) == (
        Route.escalate,
        Urgency.urgent,
        Intent.health_or_safety,
    )
    assert inquiry.updated_at == T2
    assert inquiry.created_at == T1


def test_update_refuses_to_change_status_or_unknown_fields(conn: sqlite3.Connection) -> None:
    inquiry_id = new_inquiry(conn)
    with pytest.raises(ValueError, match="status"):
        repo.update_inquiry(conn, inquiry_id, status="approved")
    with pytest.raises(ValueError, match="body"):
        repo.update_inquiry(conn, inquiry_id, body="rewritten")
    with pytest.raises(ValueError):
        repo.update_inquiry(conn, inquiry_id, route="not_a_route")


def test_update_of_a_missing_inquiry_is_an_error(conn: sqlite3.Connection) -> None:
    with pytest.raises(LookupError):
        repo.update_inquiry(conn, 999, route=Route.archive)


def test_list_inquiries_filters_by_status_and_limits(conn: sqlite3.Connection) -> None:
    ids = [new_inquiry(conn) for _ in range(4)]
    set_status(conn, ids[1], "screened")
    set_status(conn, ids[3], "screened")
    only = repo.list_inquiries(conn, statuses=[InquiryStatus.screened])
    assert [i.id for i in only] == [ids[1], ids[3]]
    assert len(repo.list_inquiries(conn, limit=2)) == 2
    assert len(repo.list_inquiries(conn)) == 4


def test_review_queue_holds_only_items_needing_attention_in_priority_order(
    conn: sqlite3.Connection,
) -> None:
    def add(status: str, urgency: str | None, received_at: str) -> int:
        inquiry_id = new_inquiry(conn, received_at=received_at)
        set_status(conn, inquiry_id, status)
        if urgency:
            conn.execute("UPDATE inquiries SET urgency = ? WHERE id = ?", (urgency, inquiry_id))
        return inquiry_id

    normal_old = add("needs_review", "normal", T1)
    urgent_new = add("escalated", "urgent", T3)
    urgent_old = add("failed", "urgent", T1)
    high = add("needs_review", "high", T2)
    low = add("needs_review", "low", T1)
    no_urgency = add("escalated", None, T1)
    add("approved", "urgent", T1)
    add("archived", "urgent", T1)
    add("screened", "urgent", T1)

    order = [i.id for i in repo.review_queue(conn)]
    assert order == [urgent_old, urgent_new, high, normal_old, low, no_urgency]


def clean_screening(conn: sqlite3.Connection, inquiry_id: int, result: ScreeningResult) -> None:
    repo.upsert_screening(
        conn,
        inquiry_id=inquiry_id,
        spam_score=0.0,
        injection_flags=[],
        sensitive_data_masked=False,
        result=result,
        now=T1,
    )


def test_a_sender_with_an_earlier_clean_inquiry_is_known(conn: sqlite3.Connection) -> None:
    earlier = new_inquiry(conn, sender_email="alex@example.com")
    clean_screening(conn, earlier, ScreeningResult.clean)
    later = new_inquiry(conn, sender_email="alex@example.com")
    assert repo.has_clean_history(conn, "alex@example.com", exclude_id=later) is True
    assert repo.has_clean_history(conn, "ALEX@example.com", exclude_id=later) is True


def test_a_sender_is_not_known_from_spam_unknown_email_or_themselves(
    conn: sqlite3.Connection,
) -> None:
    spam = new_inquiry(conn, sender_email="bot@example.com")
    clean_screening(conn, spam, ScreeningResult.spam)
    injected = new_inquiry(conn, sender_email="inj@example.com")
    clean_screening(conn, injected, ScreeningResult.injection_suspected)
    only = new_inquiry(conn, sender_email="new@example.com")
    clean_screening(conn, only, ScreeningResult.clean)
    now_id = new_inquiry(conn, sender_email="bot@example.com")
    assert repo.has_clean_history(conn, "bot@example.com", exclude_id=now_id) is False
    assert repo.has_clean_history(conn, "inj@example.com", exclude_id=now_id) is False
    assert repo.has_clean_history(conn, "nobody@example.com", exclude_id=now_id) is False
    assert repo.has_clean_history(conn, "new@example.com", exclude_id=only) is False  # only itself
    assert repo.has_clean_history(conn, None, exclude_id=now_id) is False


def test_a_duplicate_does_not_make_a_sender_known(conn: sqlite3.Connection) -> None:
    original = new_inquiry(conn, sender_email="dup@example.com")
    copy = new_inquiry(conn, sender_email="dup@example.com", duplicate_of=original)
    clean_screening(conn, copy, ScreeningResult.clean)
    probe = new_inquiry(conn, sender_email="dup@example.com")
    assert repo.has_clean_history(conn, "dup@example.com", exclude_id=probe) is False


# --- searching and paging ---------------------------------------------------------------------


def prioritised(conn: sqlite3.Connection) -> dict[str, int]:
    """Inquiries covering every urgency, in a known priority order."""
    spec = [
        ("u_old", "urgent", "2026-10-28T08:00:00Z"),
        ("u_new", "urgent", "2026-10-28T09:00:00Z"),
        ("h", "high", "2026-10-28T07:00:00Z"),
        ("n", "normal", "2026-10-28T06:00:00Z"),
        ("l", "low", "2026-10-28T05:00:00Z"),
        ("none", None, "2026-10-28T04:00:00Z"),
    ]
    ids: dict[str, int] = {}
    for name, urgency, received in spec:
        ids[name] = new_inquiry(conn, received_at=received, body=f"message {name}")
        if urgency:
            conn.execute("UPDATE inquiries SET urgency = ? WHERE id = ?", (urgency, ids[name]))
    return ids


def test_search_orders_by_urgency_then_oldest_first(conn: sqlite3.Connection) -> None:
    ids = prioritised(conn)
    order = [i.id for i in repo.search_inquiries(conn)]
    # low and "no urgency yet" share the last bucket (BACKEND_SCHEMA.md section 6), oldest first.
    assert order == [ids[k] for k in ("u_old", "u_new", "h", "n", "none", "l")]


def test_search_filters_combine(conn: sqlite3.Connection) -> None:
    ids = prioritised(conn)
    set_status(conn, ids["h"], "needs_review")
    set_status(conn, ids["u_old"], "escalated")
    conn.execute("UPDATE inquiries SET route = 'escalate' WHERE id = ?", (ids["u_old"],))
    assert [i.id for i in repo.search_inquiries(conn, statuses=["needs_review", "escalated"])] == [
        ids["u_old"],
        ids["h"],
    ]
    assert [i.id for i in repo.search_inquiries(conn, routes=["escalate"])] == [ids["u_old"]]
    assert [i.id for i in repo.search_inquiries(conn, urgencies=["urgent"])] == [
        ids["u_old"],
        ids["u_new"],
    ]
    assert repo.search_inquiries(conn, statuses=["needs_review"], urgencies=["urgent"]) == []


def test_search_text_matches_subject_body_sender_and_ignores_case(conn: sqlite3.Connection) -> None:
    a = new_inquiry(conn, subject="Leaking Toilet", body="x")
    b = new_inquiry(conn, body="the BOILER is broken")
    c = new_inquiry(conn, body="y", sender_name="Priya Raman")
    d = new_inquiry(conn, body="z", sender_email="someone@example.com")
    assert [i.id for i in repo.search_inquiries(conn, q="toilet")] == [a]
    assert [i.id for i in repo.search_inquiries(conn, q="boiler")] == [b]
    assert [i.id for i in repo.search_inquiries(conn, q="PRIYA")] == [c]
    assert [i.id for i in repo.search_inquiries(conn, q="someone@")] == [d]


@pytest.mark.parametrize("wild", ["%", "_", "\\", "50%", "a_b"])
def test_search_treats_wildcards_literally(conn: sqlite3.Connection, wild: str) -> None:
    plain = new_inquiry(conn, body="an ordinary message about a drain")
    literal = new_inquiry(conn, body=f"price is {wild} off")
    found = [i.id for i in repo.search_inquiries(conn, q=wild)]
    assert plain not in found
    assert literal in found


def test_keyset_paging_walks_every_row_once_even_as_new_ones_arrive(
    conn: sqlite3.Connection,
) -> None:
    ids = prioritised(conn)
    first = repo.search_inquiries(conn, limit=2)
    last = first[-1]
    key = (
        repo.urgency_rank(last.urgency.value if last.urgency else None),
        last.received_at,
        last.id,
    )
    newest = new_inquiry(conn, received_at="2026-10-28T23:00:00Z", body="arrived while paging")
    conn.execute("UPDATE inquiries SET urgency = 'urgent' WHERE id = ?", (newest,))
    seen = [i.id for i in first]
    after = key
    while True:
        page = repo.search_inquiries(conn, limit=2, after=after)
        if not page:
            break
        seen += [i.id for i in page]
        tail = page[-1]
        after = (
            repo.urgency_rank(tail.urgency.value if tail.urgency else None),
            tail.received_at,
            tail.id,
        )
    assert len(seen) == len(set(seen))
    assert set(ids.values()) <= set(seen)


def test_urgency_rank_puts_unknown_last() -> None:
    ranks = [repo.urgency_rank(u) for u in ("urgent", "high", "normal", "low", None)]
    assert ranks == [0, 1, 2, 3, 3]


def test_list_duplicates_of_an_inquiry(conn: sqlite3.Connection) -> None:
    original = new_inquiry(conn)
    copies = [new_inquiry(conn, duplicate_of=original) for _ in range(2)]
    other = new_inquiry(conn)
    assert repo.list_duplicates_of(conn, original) == copies
    assert repo.list_duplicates_of(conn, other) == []


# --- screenings ------------------------------------------------------------------------------


def test_screening_is_written_once_per_inquiry_and_rerun_overwrites(
    conn: sqlite3.Connection,
) -> None:
    inquiry_id = new_inquiry(conn)
    first = repo.upsert_screening(
        conn,
        inquiry_id=inquiry_id,
        spam_score=0.1,
        injection_flags=[],
        sensitive_data_masked=False,
        result=ScreeningResult.clean,
        now=T1,
    )
    second = repo.upsert_screening(
        conn,
        inquiry_id=inquiry_id,
        spam_score=0.9,
        injection_flags=["ignore_previous"],
        sensitive_data_masked=True,
        result=ScreeningResult.injection_suspected,
        now=T2,
    )
    assert first == second
    screening = repo.get_screening(conn, inquiry_id)
    assert screening is not None
    assert screening.result is ScreeningResult.injection_suspected
    assert screening.injection_flags == ["ignore_previous"]
    assert screening.sensitive_data_masked is True
    assert conn.execute("SELECT COUNT(*) FROM screenings").fetchone()[0] == 1


def test_screening_for_an_unknown_inquiry_is_refused(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        repo.upsert_screening(
            conn,
            inquiry_id=999,
            spam_score=0,
            injection_flags=[],
            sensitive_data_masked=False,
            result=ScreeningResult.clean,
        )


def test_get_screening_returns_none_when_missing(conn: sqlite3.Connection) -> None:
    assert repo.get_screening(conn, new_inquiry(conn)) is None


# --- classifications and extractions ---------------------------------------------------------


def classify(conn: sqlite3.Connection, inquiry_id: int, **over: Any) -> int:
    args: dict[str, Any] = {
        "inquiry_id": inquiry_id,
        "model": "qwen3:8b",
        "prompt_version": "understand-v1",
        "intents": [ClassifiedIntent(intent=Intent.pricing_question, confidence=Confidence.high)],
        "primary_intent": Intent.pricing_question,
        "primary_confidence": Confidence.high,
        "urgency": Urgency.normal,
        "sentiment": Sentiment.neutral,
        "summary": "Asks for a drain price.",
        "safety_net_hit": False,
        "raw_response": "{}",
        "now": T1,
    }
    return repo.insert_classification(conn, **{**args, **over})


def test_classification_attempts_count_up_and_latest_wins(conn: sqlite3.Connection) -> None:
    inquiry_id = new_inquiry(conn)
    first = classify(conn, inquiry_id)
    second = classify(conn, inquiry_id, urgency=Urgency.high, now=T2)
    attempts = [
        r["attempt"] for r in conn.execute("SELECT attempt FROM classifications ORDER BY id")
    ]
    assert attempts == [1, 2]
    latest = repo.latest_classification(conn, inquiry_id)
    assert latest is not None and latest.id == second != first
    assert latest.urgency is Urgency.high
    assert latest.intents[0].intent is Intent.pricing_question


def test_classification_attempts_are_per_inquiry(conn: sqlite3.Connection) -> None:
    a, b = new_inquiry(conn), new_inquiry(conn)
    classify(conn, a)
    classify(conn, a)
    classify(conn, b)
    latest_b = repo.latest_classification(conn, b)
    assert latest_b is not None and latest_b.attempt == 1


def test_latest_classification_is_none_when_missing(conn: sqlite3.Connection) -> None:
    assert repo.latest_classification(conn, new_inquiry(conn)) is None


FIELDS = ExtractedFields(
    service_type=None,
    start_date="2026-11-03",
    property_type=None,
    address_area="Millrace",
    preferred_contact=None,
    booking_reference=None,
    dates_as_written="Tuesday the 3rd",
)


def test_extraction_round_trip(conn: sqlite3.Connection) -> None:
    inquiry_id = new_inquiry(conn)
    classification_id = classify(conn, inquiry_id)
    repo.insert_extraction(
        conn,
        inquiry_id=inquiry_id,
        classification_id=classification_id,
        fields=FIELDS,
        missing_fields=["service_type", "property_type"],
        now=T1,
    )
    extraction = repo.latest_extraction(conn, inquiry_id)
    assert extraction is not None
    assert extraction.fields == FIELDS
    assert extraction.missing_fields == ["service_type", "property_type"]
    assert extraction.classification_id == classification_id


def test_extraction_must_belong_to_a_classification_of_the_same_inquiry(
    conn: sqlite3.Connection,
) -> None:
    a, b = new_inquiry(conn), new_inquiry(conn)
    classification_of_a = classify(conn, a)
    with pytest.raises(ValueError, match="classification"):
        repo.insert_extraction(
            conn,
            inquiry_id=b,
            classification_id=classification_of_a,
            fields=FIELDS,
            missing_fields=[],
        )


def test_latest_extraction_is_none_when_missing(conn: sqlite3.Connection) -> None:
    assert repo.latest_extraction(conn, new_inquiry(conn)) is None


# --- escalations -----------------------------------------------------------------------------


def test_escalation_round_trip_and_listing(conn: sqlite3.Connection) -> None:
    inquiry_id = new_inquiry(conn)
    repo.insert_escalation(
        conn,
        inquiry_id=inquiry_id,
        reason_code=ReasonCode.HEALTH_SAFETY,
        source=EscalationSource.safety_net,
        detail="gas smell",
        now=T1,
    )
    repo.insert_escalation(
        conn,
        inquiry_id=inquiry_id,
        reason_code=ReasonCode.COMPLAINT,
        source=EscalationSource.rule,
        now=T1,
    )
    rows = repo.list_escalations(conn, inquiry_id)
    assert [r.reason_code for r in rows] == [ReasonCode.HEALTH_SAFETY, ReasonCode.COMPLAINT]
    assert rows[0].resolved is False and rows[0].detail == "gas smell"


def test_rerunning_a_stage_does_not_duplicate_an_open_escalation(conn: sqlite3.Connection) -> None:
    inquiry_id = new_inquiry(conn)
    kwargs: dict[str, Any] = {
        "inquiry_id": inquiry_id,
        "reason_code": ReasonCode.COMPLAINT,
        "source": EscalationSource.rule,
    }
    first = repo.insert_escalation(conn, **kwargs)
    again = repo.insert_escalation(conn, **kwargs)
    assert first == again
    assert len(repo.list_escalations(conn, inquiry_id)) == 1


def test_a_resolved_escalation_can_be_raised_again(conn: sqlite3.Connection) -> None:
    inquiry_id = new_inquiry(conn)
    kwargs: dict[str, Any] = {
        "inquiry_id": inquiry_id,
        "reason_code": ReasonCode.COMPLAINT,
        "source": EscalationSource.rule,
    }
    repo.insert_escalation(conn, **kwargs)
    assert repo.resolve_escalations(conn, inquiry_id, now=T2) == 1
    repo.insert_escalation(conn, **kwargs)
    assert len(repo.list_escalations(conn, inquiry_id)) == 2
    assert len(repo.list_escalations(conn, inquiry_id, open_only=True)) == 1


def test_resolve_marks_every_open_escalation(conn: sqlite3.Connection) -> None:
    inquiry_id = new_inquiry(conn)
    for code in (ReasonCode.COMPLAINT, ReasonCode.REFUND_OR_DISPUTE):
        repo.insert_escalation(
            conn, inquiry_id=inquiry_id, reason_code=code, source=EscalationSource.rule
        )
    assert repo.resolve_escalations(conn, inquiry_id, now=T2) == 2
    rows = repo.list_escalations(conn, inquiry_id)
    assert all(r.resolved and r.resolved_at == T2 for r in rows)
    assert repo.resolve_escalations(conn, inquiry_id, now=T3) == 0


def test_escalation_detail_must_be_short(conn: sqlite3.Connection) -> None:
    inquiry_id = new_inquiry(conn)
    with pytest.raises(ValueError, match="detail"):
        repo.insert_escalation(
            conn,
            inquiry_id=inquiry_id,
            reason_code=ReasonCode.MANUAL,
            source=EscalationSource.reviewer,
            detail="x" * 201,
        )


# --- retrievals ------------------------------------------------------------------------------


def test_retrieval_round_trip(conn: sqlite3.Connection) -> None:
    inquiry_id = new_inquiry(conn)
    sources = [
        Source(file="pricing.md", section="Pricing > Drain cleaning", page=None, text="$149")
    ]
    repo.insert_retrieval(
        conn,
        inquiry_id=inquiry_id,
        question="How much is drain cleaning?",
        declined=False,
        kb_answer="From $149.",
        sources=sources,
        duration_ms=800,
        now=T1,
    )
    repo.insert_retrieval(
        conn,
        inquiry_id=inquiry_id,
        question="Anyone free Friday?",
        declined=True,
        kb_answer=None,
        sources=[],
        duration_ms=None,
        now=T2,
    )
    rows = repo.list_retrievals(conn, inquiry_id)
    assert [r.declined for r in rows] == [False, True]
    assert rows[0].sources == sources and rows[0].sources[0].page is None
    assert rows[1].sources == [] and rows[1].kb_answer is None


# --- drafts and checks -----------------------------------------------------------------------


def test_draft_versions_count_up_per_inquiry(conn: sqlite3.Connection) -> None:
    a, b = new_inquiry(conn), new_inquiry(conn)
    new_draft(conn, a)
    second = new_draft(conn, a)
    only_b = new_draft(conn, b)
    drafts_a = repo.list_drafts(conn, a)
    assert [d.version for d in drafts_a] == [1, 2]
    latest = repo.latest_draft(conn, a)
    assert latest is not None and latest.id == second
    other = repo.get_draft(conn, only_b)
    assert other is not None and other.version == 1


def test_a_new_draft_starts_blocked_not_ready(conn: sqlite3.Connection) -> None:
    draft = repo.get_draft(conn, new_draft(conn, new_inquiry(conn)))
    assert draft is not None
    assert draft.status is DraftStatus.blocked


def test_draft_claims_and_guidance_round_trip(conn: sqlite3.Connection) -> None:
    claims = [Claim(text="Drain cleaning starts at $149", source_index=0)]
    draft_id = new_draft(
        conn, new_inquiry(conn), claims=claims, guidance="shorter", subject="Re: drain"
    )
    draft = repo.get_draft(conn, draft_id)
    assert draft is not None
    assert (draft.claims, draft.guidance, draft.subject) == (claims, "shorter", "Re: drain")


def test_supersede_older_drafts_keeps_the_chosen_one(conn: sqlite3.Connection) -> None:
    inquiry_id = new_inquiry(conn)
    first, second, third = (new_draft(conn, inquiry_id) for _ in range(3))
    repo.set_draft_status(conn, third, DraftStatus.ready)
    repo.supersede_older_drafts(conn, inquiry_id, keep_id=third)
    status = {d.id: d.status for d in repo.list_drafts(conn, inquiry_id)}
    assert status == {
        first: DraftStatus.superseded,
        second: DraftStatus.superseded,
        third: DraftStatus.ready,
    }


def add_check(
    conn: sqlite3.Connection, draft_id: int, code: CheckCode, *, blocking: bool, passed: bool
) -> None:
    repo.upsert_draft_check(
        conn, draft_id=draft_id, check_code=code, blocking=blocking, passed=passed, now=T1
    )


def test_draft_check_is_one_row_per_code_and_rerun_overwrites(conn: sqlite3.Connection) -> None:
    draft_id = new_draft(conn, new_inquiry(conn))
    add_check(conn, draft_id, CheckCode.FIGURES_GROUNDED, blocking=True, passed=False)
    repo.upsert_draft_check(
        conn,
        draft_id=draft_id,
        check_code=CheckCode.FIGURES_GROUNDED,
        blocking=True,
        passed=True,
        detail={"grounded": ["$149"]},
        now=T2,
    )
    checks = repo.list_draft_checks(conn, draft_id)
    assert len(checks) == 1
    assert checks[0].passed is True and checks[0].detail == {"grounded": ["$149"]}


def test_blocking_failures_lists_only_failed_blocking_checks(conn: sqlite3.Connection) -> None:
    draft_id = new_draft(conn, new_inquiry(conn))
    add_check(conn, draft_id, CheckCode.FIGURES_GROUNDED, blocking=True, passed=False)
    add_check(conn, draft_id, CheckCode.NO_COMMITMENT, blocking=True, passed=True)
    add_check(conn, draft_id, CheckCode.STRUCTURE, blocking=False, passed=False)
    assert repo.blocking_failures(conn, draft_id) == [CheckCode.FIGURES_GROUNDED]


@pytest.mark.parametrize("status", [DraftStatus.ready, DraftStatus.approved])
def test_a_draft_with_a_failed_blocking_check_can_never_be_ready_or_approved(
    conn: sqlite3.Connection, status: DraftStatus
) -> None:
    draft_id = new_draft(conn, new_inquiry(conn))
    add_check(conn, draft_id, CheckCode.NO_COMMITMENT, blocking=True, passed=False)
    with pytest.raises(repo.DraftBlocked, match="NO_COMMITMENT"):
        repo.set_draft_status(conn, draft_id, status)
    draft = repo.get_draft(conn, draft_id)
    assert draft is not None and draft.status is DraftStatus.blocked


def test_a_draft_may_be_ready_when_only_non_blocking_checks_failed(
    conn: sqlite3.Connection,
) -> None:
    draft_id = new_draft(conn, new_inquiry(conn))
    add_check(conn, draft_id, CheckCode.STRUCTURE, blocking=False, passed=False)
    add_check(conn, draft_id, CheckCode.NO_COMMITMENT, blocking=True, passed=True)
    repo.set_draft_status(conn, draft_id, DraftStatus.ready)
    draft = repo.get_draft(conn, draft_id)
    assert draft is not None and draft.status is DraftStatus.ready


@pytest.mark.parametrize(
    "status", [DraftStatus.blocked, DraftStatus.rejected, DraftStatus.superseded]
)
def test_a_blocked_draft_can_always_move_to_a_safe_status(
    conn: sqlite3.Connection, status: DraftStatus
) -> None:
    draft_id = new_draft(conn, new_inquiry(conn))
    add_check(conn, draft_id, CheckCode.FIGURES_GROUNDED, blocking=True, passed=False)
    repo.set_draft_status(conn, draft_id, status)
    draft = repo.get_draft(conn, draft_id)
    assert draft is not None and draft.status is status


def test_set_status_of_a_missing_draft_is_an_error(conn: sqlite3.Connection) -> None:
    with pytest.raises(LookupError):
        repo.set_draft_status(conn, 999, DraftStatus.blocked)


# --- reviews and exports ---------------------------------------------------------------------


def test_reviews_round_trip_and_summaries(conn: sqlite3.Connection) -> None:
    inquiry_id = new_inquiry(conn)
    draft_id = new_draft(conn, inquiry_id)
    repo.insert_review(
        conn,
        inquiry_id=inquiry_id,
        draft_id=draft_id,
        decision=Decision.approve,
        review_seconds=40,
        now=T1,
    )
    repo.insert_review(
        conn,
        inquiry_id=inquiry_id,
        draft_id=draft_id,
        decision=Decision.edit_approve,
        edited_body="edited",
        review_seconds=90,
        now=T2,
    )
    repo.insert_review(
        conn,
        inquiry_id=inquiry_id,
        draft_id=draft_id,
        decision=Decision.reject,
        reason="wrong price",
        now=T3,
    )
    repo.insert_review(
        conn, inquiry_id=inquiry_id, decision=Decision.escalate, review_seconds=15, now=T3
    )
    reviews = repo.list_reviews(conn, inquiry_id)
    assert [r.decision for r in reviews] == [
        Decision.approve,
        Decision.edit_approve,
        Decision.reject,
        Decision.escalate,
    ]
    assert reviews[0].reviewer == "local"
    assert reviews[1].edited_body == "edited" and reviews[2].reason == "wrong price"
    assert reviews[3].draft_id is None
    assert repo.decision_counts(conn) == {
        Decision.approve: 1,
        Decision.edit_approve: 1,
        Decision.reject: 1,
        Decision.escalate: 1,
    }
    assert sorted(repo.approval_review_seconds(conn)) == [40, 90]


def test_exports_record_how_text_left_the_tool(conn: sqlite3.Connection) -> None:
    draft_id = new_draft(conn, new_inquiry(conn))
    repo.insert_export(conn, draft_id=draft_id, method=ExportMethod.copy, now=T1)
    repo.insert_export(
        conn, draft_id=draft_id, method=ExportMethod.mail_draft, external_ref="draft-123", now=T2
    )
    exports = repo.list_exports(conn, draft_id)
    assert [e.method for e in exports] == [ExportMethod.copy, ExportMethod.mail_draft]
    assert exports[1].external_ref == "draft-123"


def test_there_is_no_way_to_record_a_sent_message(conn: sqlite3.Connection) -> None:
    draft_id = new_draft(conn, new_inquiry(conn))
    with pytest.raises(ValueError):
        repo.insert_export(conn, draft_id=draft_id, method="sent")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO exports (draft_id, method, created_at) VALUES (?, 'sent', 'x')",
            (draft_id,),
        )


# --- settings --------------------------------------------------------------------------------


def test_settings_get_set_and_overwrite(conn: sqlite3.Connection) -> None:
    assert repo.get_setting(conn, "spam_threshold") is None
    repo.set_setting(conn, "spam_threshold", "0.8", now=T1)
    assert repo.get_setting(conn, "spam_threshold") == "0.8"
    repo.set_setting(conn, "spam_threshold", "0.9", now=T2)
    assert repo.get_setting(conn, "spam_threshold") == "0.9"
    row = conn.execute("SELECT updated_at FROM settings WHERE key = 'spam_threshold'").fetchone()
    assert row["updated_at"] == T2
    assert conn.execute("SELECT COUNT(*) FROM settings").fetchone()[0] == 1
