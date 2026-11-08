"""Review figures that measure draft quality from use (D-095): how much a reviewer changed, how
often a draft was rejected, and whether drafts with a warning were changed more often.

Counts and shares only. The text of a draft and of its edit is compared in memory and never leaves
the function that compares it.
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from citedesk import repo, review
from citedesk.config import Settings
from citedesk.insights import changed_share
from citedesk.models import CheckCode
from tests.helpers import DRAFT_BODY, in_review
from tests.test_api_review import database


def test_an_unchanged_text_has_nothing_changed() -> None:
    assert changed_share(DRAFT_BODY, DRAFT_BODY) == 0.0


def test_a_rewritten_text_is_wholly_changed() -> None:
    assert changed_share("one two three four", "five six seven eight") == 1.0


def test_one_word_of_ten_changed_is_about_a_tenth() -> None:
    before = "a b c d e f g h i j"
    after = "a b c d e f g h i k"
    assert changed_share(before, after) == pytest.approx(0.1)


def test_spacing_and_line_breaks_alone_change_nothing() -> None:
    assert changed_share("Hello,\n\nThanks.", "Hello,  Thanks.") == 0.0


def test_an_empty_draft_counts_as_wholly_changed_when_text_is_added() -> None:
    assert changed_share("", "new words") == 1.0
    assert changed_share("", "") == 0.0


def warn(conn: Any, draft_id: int) -> None:
    repo.upsert_draft_check(
        conn, draft_id=draft_id, check_code=CheckCode.STRUCTURE, blocking=False, passed=False
    )


def test_insights_report_edit_size_rejections_and_warnings(
    client: TestClient, api_settings: Settings
) -> None:
    with database(api_settings) as conn:
        drafts = [in_review(conn)[1] for _ in range(5)]
        warn(conn, drafts[2])
        warn(conn, drafts[3])
        review.approve(conn, drafts[0])  # clean, unchanged
        review.approve(conn, drafts[1])  # clean, unchanged
        edited = DRAFT_BODY.replace("$175", "$149")  # one word of 13 changed
        review.approve(conn, drafts[2], edited_body=edited)  # warned, edited
        review.approve(conn, drafts[3])  # warned, unchanged
        review.reject(conn, drafts[4], reason="Wrong price")
    body = client.get("/api/insights").json()
    assert body["reject_share"] == pytest.approx(1 / 5)
    assert body["edit_size_sample"] == 1
    assert 0 < body["median_edit_share"] < 0.2
    assert (body["warned_approvals"], body["warned_unchanged"]) == (2, 1)
    assert (body["clean_approvals"], body["clean_unchanged"]) == (2, 2)


def test_insights_on_an_empty_database_have_no_quality_figures(client: TestClient) -> None:
    body = client.get("/api/insights").json()
    assert body["reject_share"] is None
    assert body["median_edit_share"] is None
    assert body["edit_size_sample"] == 0
    assert body["warned_approvals"] == body["clean_approvals"] == 0


def test_the_insights_answer_holds_no_draft_or_edit_text(
    client: TestClient, api_settings: Settings
) -> None:
    marker = "UNIQUE-EDIT-WORDS-12345"
    with database(api_settings) as conn:
        _, draft_id = in_review(conn)
        review.approve(conn, draft_id, edited_body=f"Hello,\n\n{marker}\n\nKind regards,\nB")
    assert marker not in client.get("/api/insights").text
