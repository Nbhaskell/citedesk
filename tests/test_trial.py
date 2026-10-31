"""The reviewer trial tools (docs/REVIEW_TRIAL.md), tested with a scripted model and knowledge base.

No real model is used and no held-out item is read: the items are the tuned set.
"""

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from citedesk import repo, review
from citedesk.business import Business
from citedesk.config import Settings
from citedesk.db import connect, migrate
from citedesk.knowledge import FakeKB
from citedesk.models import InquiryStatus
from citedesk.providers import FakeLLM
from citedesk.providers.fake import LLMCall
from tests.golden_data import tuned_golden
from tests.helpers import model_reply
from tools import trial_plants as plants
from tools import trial_prepare as prep
from tools import trial_score as score

S = InquiryStatus
BUSINESS = Business("Kestrel Hollow Plumbing", "555-0171", "555-0172", "kestrelhollow@example.com")
PASSAGE = "Drain cleaning, one fixture: $149 (starting price). Main sewer line cleaning: $329."


@pytest.fixture
def conn() -> sqlite3.Connection:
    c = connect(":memory:")
    migrate(c)
    return c


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None)


def llm() -> FakeLLM:
    draft = {
        "subject": "Re: Your question",
        "body": "Hello Alex,\n\nDrain cleaning for one fixture starts at $149. A member of our "
        "team "
        "will confirm a visit time with you.\n\nKind regards,\nKestrel Hollow Plumbing",
        "claims": [{"text": "starts at $149", "source_index": 0}],
    }

    def reply(call: LLMCall) -> Any:
        return draft if "claims" in json.dumps(call.schema) else model_reply()

    return FakeLLM(reply)


def kb() -> FakeKB:
    return FakeKB(lambda q: FakeKB.answered("It starts at $149.", ["pricing.md"], text=PASSAGE))


def tuned_items() -> list[dict[str, Any]]:
    return tuned_golden()["items"]


def prepared(conn: sqlite3.Connection, settings: Settings, **over: Any) -> dict[str, Any]:
    return prep.prepare(conn, settings, llm(), kb(), BUSINESS, tuned_items(), seed=7, **over)


# --- the planted problems ----------------------------------------------------------------------

CONTEXT = plants.Context(
    body="Hello Alex,\n\nA drain clearing starts at $149.\n\nKind regards,\nKestrel Hollow",
    customer_name="Alex Rivera",
    message="How much to clear a kitchen drain?",
    sources_text=PASSAGE,
)


@pytest.mark.parametrize("kind", list(plants.KINDS))
def test_every_kind_changes_the_draft_and_names_what_a_fix_must_remove(kind: str) -> None:
    plant = plants.make(kind, CONTEXT)
    assert plant is not None and plant.kind == kind
    assert plant.body != CONTEXT.body and plant.marker in plant.body
    assert plant.body.rstrip().endswith("Kestrel Hollow")  # the sign-off is still last


def test_a_wrong_name_is_never_one_the_customer_used() -> None:
    context = plants.Context(
        body="Hi Jordan,\n\nHello.",
        customer_name="Jordan Lee",
        message="I am Morgan",
        sources_text="",
    )
    plant = plants.make("wrong_name", context)
    assert plant is not None and plant.marker not in {"Jordan", "Morgan"}


def test_a_kind_that_does_not_fit_gives_nothing() -> None:
    no_greeting = plants.Context("The price is $149.", "A", "q", PASSAGE)
    assert plants.make("wrong_name", no_greeting) is None
    no_other_price = plants.Context("Costs $149.", "A", "q", "Drain: $149")
    assert plants.make("wrong_service_price", no_other_price) is None


# --- preparation -------------------------------------------------------------------------------


def test_the_trial_has_the_planned_shape(conn: sqlite3.Connection, settings: Settings) -> None:
    plan = prepared(conn, settings)
    roles = [row["role"] for row in plan["order"]]
    assert roles[:4] == ["warmup"] * 4
    assert roles.count("planted") == 6 and set(roles) == {"warmup", "ordinary", "planted"}
    assert len(roles) == 4 + plan["counts"]["ordinary"] + 6
    assert {row["kind"] for row in plan["order"] if row["role"] == "planted"} == set(plants.KINDS)
    assert all(row["kind"] is None for row in plan["order"] if row["role"] != "planted")


def test_every_inquiry_waits_for_review_with_a_ready_draft_and_only_those_remain(
    conn: sqlite3.Connection, settings: Settings
) -> None:
    plan = prepared(conn, settings)
    ids = [row["inquiry_id"] for row in plan["order"]]
    assert sorted(int(r["id"]) for r in conn.execute("SELECT id FROM inquiries")) == sorted(ids)
    for inquiry_id in ids:
        inquiry = repo.get_inquiry(conn, inquiry_id)
        draft = repo.latest_draft(conn, inquiry_id)
        assert inquiry is not None and draft is not None
        assert inquiry.status is S.needs_review and draft.status.value == "ready"
        assert repo.blocking_failures(conn, draft.id) == []  # a plant passes every blocking check


def test_a_planted_draft_contains_its_marker_and_an_ordinary_one_does_not(
    conn: sqlite3.Connection, settings: Settings
) -> None:
    plan = prepared(conn, settings)
    for row in plan["order"]:
        draft = repo.latest_draft(conn, row["inquiry_id"])
        assert draft is not None
        if row["role"] == "planted":
            assert row["marker"] in draft.body
        else:
            assert row["marker"] is None


def test_the_queue_order_is_the_plan_order(conn: sqlite3.Connection, settings: Settings) -> None:
    plan = prepared(conn, settings)
    received = {
        int(r["id"]): r["received_at"]
        for r in conn.execute("SELECT id, received_at FROM inquiries")
    }
    in_plan_order = [received[row["inquiry_id"]] for row in plan["order"]]
    assert in_plan_order == sorted(in_plan_order) and len(set(in_plan_order)) == len(in_plan_order)


def test_the_same_seed_gives_the_same_trial(settings: Settings) -> None:
    def build() -> list[tuple[str, str | None]]:
        c = connect(":memory:")
        migrate(c)
        plan = prepared(c, settings)
        return [(row["item_id"], row["kind"]) for row in plan["order"]]

    assert build() == build()


def test_only_tuned_items_are_candidates() -> None:
    chosen = prep.candidates(tuned_items())
    assert chosen and all(i["split"] == "tuned" for i in chosen)
    assert all(i["labels"]["urgency"] == "normal" for i in chosen)


def test_a_kind_that_no_draft_can_take_stops_the_preparation(
    conn: sqlite3.Connection, settings: Settings
) -> None:
    bare = FakeKB(lambda q: FakeKB.answered("It starts at $149.", ["pricing.md"], text="$149"))
    with pytest.raises(prep.PreparationError, match="wrong_service_price"):
        prep.prepare(conn, settings, llm(), bare, BUSINESS, tuned_items(), seed=7)


# --- scoring -----------------------------------------------------------------------------------


def decide(conn: sqlite3.Connection, plan: dict[str, Any], choices: dict[int, Any]) -> None:
    """Record the reviewer's decisions: position -> (decision, seconds) or (edit, seconds, text)."""
    for row in plan["order"]:
        choice = choices.get(row["position"])
        if choice is None:
            continue
        draft = repo.latest_draft(conn, row["inquiry_id"])
        assert draft is not None
        decision, seconds, *edited = choice
        if decision == "approve":
            review.approve(conn, draft.id, review_seconds=seconds)
        elif decision == "edit_approve":
            review.approve(conn, draft.id, edited_body=edited[0], review_seconds=seconds)
        elif decision == "reject":
            review.reject(conn, draft.id, reason="not right", review_seconds=seconds)


def test_catching_a_planted_problem_means_not_letting_it_through(
    conn: sqlite3.Connection, settings: Settings
) -> None:
    plan = prepared(conn, settings)
    planted = [row for row in plan["order"] if row["role"] == "planted"]
    fixed_text = repo.latest_draft(conn, planted[1]["inquiry_id"])
    assert fixed_text is not None
    choices: dict[int, Any] = {
        planted[0]["position"]: ("approve", 30),  # let through
        planted[1]["position"]: (
            "edit_approve",
            40,
            fixed_text.body.replace(planted[1]["marker"], ""),
        ),  # fixed
        planted[2]["position"]: ("edit_approve", 40, fixed_text.body),  # edited, problem left
        planted[3]["position"]: ("reject", 20),  # caught
    }
    decide(conn, plan, choices)
    result = score.score(conn, plan)
    by_position = {r["position"]: r["caught"] for r in result["rows"] if r["role"] == "planted"}
    assert by_position[planted[0]["position"]] is False
    assert by_position[planted[1]["position"]] is True
    assert by_position[planted[3]["position"]] is True
    assert by_position[planted[4]["position"]] is None  # never reviewed
    assert result["planted_caught"]["of"] == 6 and result["planted_caught"]["reviewed"] == 4


def test_timing_uses_the_scored_drafts_and_can_leave_one_out(
    conn: sqlite3.Connection, settings: Settings
) -> None:
    plan = prepared(conn, settings)
    scored = [row for row in plan["order"] if row["role"] != "warmup"]
    warm = [row for row in plan["order"] if row["role"] == "warmup"]
    choices = {row["position"]: ("approve", 10 * n) for n, row in enumerate(scored, start=1)}
    choices[warm[0]["position"]] = ("approve", 999)
    decide(conn, plan, choices)
    result = score.score(conn, plan)
    assert result["all_scored_time"]["n"] == len(scored)  # the warm-up is not counted
    assert result["all_scored_time"]["max"] == 10 * len(scored)
    left_out = scored[-1]["inquiry_id"]
    again = score.score(conn, plan, exclude={left_out})
    assert again["all_scored_time"]["n"] == len(scored) - 1
    assert again["excluded_from_timing"] == [left_out]


def test_the_exact_interval_is_sane() -> None:
    low, high = score.exact_interval(3, 6)
    assert 0.11 < low < 0.13 and 0.87 < high < 0.89  # the standard 3-of-6 interval
    assert score.exact_interval(0, 6)[0] == 0.0 and score.exact_interval(6, 6)[1] == 1.0
    assert score.exact_interval(0, 0) == (0.0, 1.0)


def test_percentiles_and_timing() -> None:
    assert score.percentile([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 0.9) == 9.0
    assert score.timing([]) == {"n": 0, "median": None, "p90": None, "min": None, "max": None}


def test_the_report_has_no_message_or_draft_text_and_states_its_limits(
    conn: sqlite3.Connection, settings: Settings, tmp_path: Path
) -> None:
    plan = prepared(conn, settings)
    decide(conn, plan, {row["position"]: ("approve", 25) for row in plan["order"]})
    result = score.score(conn, plan, unaided=[120, 90, 150])
    text = score.markdown(result) + json.dumps(result)
    for row in plan["order"]:
        inquiry = repo.get_inquiry(conn, row["inquiry_id"])
        draft = repo.latest_draft(conn, row["inquiry_id"])
        assert inquiry is not None and draft is not None
        assert inquiry.body[:40] not in text and draft.body[:40] not in text
        if row["marker"]:
            assert row["marker"] not in text
    assert "What this cannot tell you" in text and "One reviewer" in text
    assert "SYNTHETIC DATA" in text and "median" in text.lower()
