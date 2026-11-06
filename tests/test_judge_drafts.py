"""The judging tool (D-079) with a scripted judge: no model, no citeCheck, no network."""

import json
from pathlib import Path
from typing import Any

import pytest

from tools import judge_drafts as jd

PASSAGE = "Drain cleaning, one fixture: $149 (starting price)."
GOLDEN = {
    "a": {"id": "a", "subject": "Price", "body": "How much to clear my sink?"},
    "b": {"id": "b", "subject": None, "body": "Do you clear toilets?"},
    "c": {"id": "c", "subject": "x", "body": "y"},
}


def item(item_id: str, body: str, kind: str = "reply", declined: bool = False) -> dict[str, Any]:
    return {
        "id": item_id,
        "draft": {"kind": kind, "body": body},
        "retrievals": [{"declined": declined, "sources": [source()]}],
    }


def source(text: str = PASSAGE) -> dict[str, Any]:
    return {"file": "pricing.md", "section": "Pricing > Drains", "page": None, "text": text}


class ScriptedJudge:
    def __init__(self, verdicts: dict[str, str] | None = None, default: str = "supported") -> None:
        self.verdicts = verdicts or {}
        self.default = default
        self.calls: list[dict[str, Any]] = []

    def verdict(self, kind: str, **fields: Any) -> dict[str, Any]:
        self.calls.append({"kind": kind, **fields})
        answer = fields["answer"]
        verdict = next((v for key, v in self.verdicts.items() if key in answer), self.default)
        claims = [] if verdict == "supported" else ["a claim"]
        return {"verdict": verdict, "unsupported_claims": claims, "cached": False, "error": None}


RUN = {
    "items": [
        item("a", "Hi Ann,\n\nDrain cleaning starts at $149.\n\nKind regards,\nKestrel Hollow"),
        item("b", "Hello Bo, we can help. Kind regards, Kestrel Hollow"),
        item("c", "Hi,\n\nx\n\nKind regards,\nK", kind="request_details"),
        {"id": "zz", "draft": None, "retrievals": []},
    ]
}


# --- the cases ---------------------------------------------------------------------------------


def test_only_model_written_replies_of_known_items_become_cases() -> None:
    cases = jd.build_cases([RUN], GOLDEN)
    assert [c["id"] for c in cases] == ["a", "b"]


def test_the_draft_is_judged_without_its_greeting_and_sign_off() -> None:
    cases = jd.build_cases([RUN], GOLDEN)
    assert cases[0]["answer"] == "Drain cleaning starts at $149."
    assert cases[1]["answer"] == "We can help."  # a flat run-on is cleaned the same way
    assert "Kind regards" not in cases[1]["answer"]


def test_the_question_is_the_customers_subject_and_message_and_the_passages_are_the_sources() -> (
    None
):
    case = jd.build_cases([RUN], GOLDEN)[0]
    assert case["question"] == "Price\nHow much to clear my sink?"
    assert case["passages"] == [PASSAGE]


def test_a_declined_retrieval_gives_no_passages() -> None:
    run = {"items": [item("a", "Hi,\n\nWe do.\n\nKind regards,\nK", declined=True)]}
    assert jd.build_cases([run], GOLDEN)[0]["passages"] == []


def test_the_same_draft_in_two_runs_is_one_case() -> None:
    assert len(jd.build_cases([RUN, RUN], GOLDEN)) == 2


# --- judging and the summary -------------------------------------------------------------------


def test_the_judge_is_asked_the_faithfulness_question_with_the_passages() -> None:
    judge = ScriptedJudge()
    results = jd.judge_all(judge, jd.build_cases([RUN], GOLDEN))
    assert [r["verdict"] for r in results] == ["supported", "supported"]
    assert judge.calls[0]["kind"] == "faithfulness" and judge.calls[0]["passages"] == [PASSAGE]
    assert judge.calls[0]["answer"] == "Drain cleaning starts at $149."


def test_the_summary_counts_verdicts_and_names_the_flagged_ids() -> None:
    results = [
        {"id": "a", "verdict": "supported"},
        {"id": "b", "verdict": "partly_supported"},
        {"id": "c", "verdict": "unsupported"},
        {"id": "d", "verdict": None},
    ]
    summary = jd.summarise(results)
    assert summary["counts"] == {"supported": 1, "partly_supported": 1, "unsupported": 1}
    assert (summary["judged"], summary["errors"]) == (3, 1)
    assert summary["mean"] == pytest.approx(0.5)
    assert summary["flagged_ids"] == ["b", "c"]


def test_the_printed_summary_has_ids_and_counts_and_no_draft_text() -> None:
    judge = ScriptedJudge({"149": "partly_supported"})
    cases = jd.build_cases([RUN], GOLDEN)
    text = jd.render_summary(jd.summarise(jd.judge_all(judge, cases)), {"model": "m"})
    assert "flagged (not fully supported): a" in text
    assert "Drain cleaning" not in text and "How much" not in text


# --- known-bad ---------------------------------------------------------------------------------


def good_cases() -> list[dict[str, Any]]:
    return [
        {
            "id": f"g{n}",
            "question": "q",
            "answer": f"Drain cleaning starts at $149. Case {n}.",
            "passages": [PASSAGE],
        }
        for n in range(8)
    ]


def test_each_kind_of_damage_is_applied_to_that_many_different_drafts() -> None:
    plants = jd.load_plants()
    damaged = jd.damaged_cases(good_cases(), plants, per_kind=3)
    kinds = {d["damage"] for d in damaged}
    assert kinds == {*plants, "price_changed"} and "wrong_service_price" not in kinds
    for kind in kinds:
        ids = [d["id"] for d in damaged if d["damage"] == kind]
        assert len(ids) == 3 and len(set(ids)) == 3


def test_damage_changes_the_answer_and_keeps_the_rest() -> None:
    damaged = jd.damaged_cases(good_cases(), jd.load_plants(), per_kind=1)
    for case in damaged:
        original = next(g for g in good_cases() if g["id"] == case["id"])["answer"]
        assert case["answer"] != original
        assert case["passages"] == [PASSAGE]
    price = next(d for d in damaged if d["damage"] == "price_changed")
    assert "$199" in price["answer"] and "$149" not in price["answer"]


def test_a_draft_with_no_price_cannot_have_its_price_changed() -> None:
    cases = [{"id": "x", "question": "q", "answer": "We can help.", "passages": []}]
    damaged = jd.damaged_cases(cases, {}, per_kind=1)
    assert damaged == []


def test_the_known_bad_summary_counts_what_was_flagged_per_kind() -> None:
    controls = [{"id": "g1", "verdict": "supported"}, {"id": "g2", "verdict": "partly_supported"}]
    damaged = [
        {"id": "g1", "damage": "invented_perk", "verdict": "unsupported"},
        {"id": "g2", "damage": "invented_perk", "verdict": "supported"},
        {"id": "g1", "damage": "price_changed", "verdict": "partly_supported"},
    ]
    summary = jd.known_bad_summary(controls, damaged)
    assert summary["control"] == (1, 2)
    assert summary["kinds"] == {"invented_perk": (1, 2), "price_changed": (1, 1)}
    assert "invented_perk: flagged 1 of 2" in jd.render_known_bad(summary)


# --- hand labels -------------------------------------------------------------------------------


def results_of(n_flagged: int, n_fine: int) -> list[dict[str, Any]]:
    return [{"id": f"f{i}", "verdict": "unsupported"} for i in range(n_flagged)] + [
        {"id": f"s{i}", "verdict": "supported"} for i in range(n_fine)
    ]


def test_the_sheet_sample_mixes_flagged_and_unflagged_and_is_repeatable() -> None:
    results = results_of(10, 30)
    order = jd.sample_for_sheet(results, 12, seed=1)
    assert len(order) == len(set(order)) == 12
    flagged = sum(results[i]["verdict"] != "supported" for i in order)
    assert flagged == 6
    assert order == jd.sample_for_sheet(results, 12, seed=1)


def test_the_sheet_shows_the_message_passages_and_draft_and_no_verdict() -> None:
    cases = jd.build_cases([RUN], GOLDEN)
    results = [
        {"id": c["id"], "verdict": "unsupported", "unsupported_claims": ["SECRET CLAIM"]}
        for c in cases
    ]
    text = jd.sheet_markdown(cases, results, [1, 0])
    assert "How much to clear my sink?" in text and PASSAGE in text and "We can help." in text
    assert "SECRET CLAIM" not in text and "unsupported_claims" not in text
    assert text.index("`b`") < text.index("`a`")  # the order given


def test_agreement_counts_exact_matches_and_both_kinds_of_miss() -> None:
    labels = {"a": "supported", "b": "supported", "c": "unsupported", "d": "partly_supported"}
    results = [
        {"id": "a", "verdict": "supported"},
        {"id": "b", "verdict": "unsupported"},
        {"id": "c", "verdict": "supported"},
        {"id": "d", "verdict": "partly_supported"},
        {"id": "e", "verdict": "supported"},
    ]
    result = jd.agreement(labels, results)
    assert (result["n"], result["exact"], result["same_side"]) == (4, 2, 2)
    assert result["judge_flags_what_hand_calls_supported"] == 1
    assert result["judge_passes_what_hand_flags"] == 1
    assert result["matrix"]["supported -> unsupported"] == 1


def test_kappa_is_none_when_one_side_uses_a_single_label() -> None:
    assert jd.cohens_kappa([("supported", "supported")] * 5) is None
    assert jd.cohens_kappa([("a", "a"), ("b", "b")]) == pytest.approx(1.0)


# --- the files -----------------------------------------------------------------------------------


def test_the_planted_sentence_set_loads_by_kind() -> None:
    plants = jd.load_plants()
    assert {"invented_perk", "unlisted_credit", "soft_commitment", "setup_disclosure"} <= set(
        plants
    )
    assert all(len(v) >= 3 for v in plants.values())


def test_a_missing_citecheck_folder_is_a_clear_refusal(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="not found"):
        jd.load_citecheck(tmp_path / "nowhere")


def test_main_needs_the_judged_file_for_the_later_commands(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert jd.main(["known-bad"]) == 2
    assert "--judged" in capsys.readouterr().err


def test_main_calibrates_from_a_labels_file_without_a_model(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    judged = tmp_path / "judged.json"
    rows = results_of(1, 1)
    judged.write_text(
        json.dumps({"cases": [{"id": r["id"]} for r in rows], "results": rows}), encoding="utf-8"
    )
    labels = tmp_path / "labels.json"
    labels.write_text(
        json.dumps({"labeller": "x", "labels": {"f0": "unsupported", "s0": "supported"}}),
        encoding="utf-8",
    )
    assert jd.main(["calibrate", "--judged", str(judged), "--labels", str(labels)]) == 0
    assert json.loads(capsys.readouterr().out)["exact"] == 2


def test_the_sheet_says_that_sentences_which_only_manage_the_conversation_are_not_claims() -> None:
    text = jd.sheet_markdown([], [], [])
    assert "not a claim" in text and "follow up" in text


def test_a_labels_template_lists_the_ids_in_sheet_order_and_empty_labels_are_ignored() -> None:
    template = jd.label_template(["b", "a"])
    assert list(template["labels"]) == ["b", "a"] and set(template["labels"].values()) == {""}
    results = [{"id": "a", "verdict": "supported"}, {"id": "b", "verdict": "unsupported"}]
    assert jd.agreement({"a": "supported", "b": ""}, results)["n"] == 1


# --- the same inquiry drafted twice ------------------------------------------------------------


def test_a_repeated_id_gets_a_suffix_so_each_draft_can_be_labelled_on_its_own() -> None:
    assert jd.unique_ids(["a", "b", "a", "a", "c"]) == ["a", "b", "a~2", "a~3", "c"]


def test_the_template_keeps_labels_already_written_and_adds_the_missing_ones() -> None:
    existing = {"labeller": "Pat", "labels": {"a": "supported", "b": ""}}
    merged = jd.merge_template(existing, ["a", "b", "a~2"])
    assert merged["labeller"] == "Pat"
    assert merged["labels"] == {"a": "supported", "b": "", "a~2": ""}


def test_the_template_never_drops_a_label_the_sheet_no_longer_lists() -> None:
    merged = jd.merge_template({"labeller": "", "labels": {"gone": "unsupported"}}, ["a"])
    assert merged["labels"]["gone"] == "unsupported" and "a" in merged["labels"]


def test_saved_cases_and_results_are_renamed_together_by_position() -> None:
    cases = [{"id": "a"}, {"id": "a"}]
    results = [{"id": "a", "verdict": "supported"}, {"id": "a", "verdict": "unsupported"}]
    jd.apply_unique_ids(cases, results)
    assert [c["id"] for c in cases] == ["a", "a~2"]
    assert [r["id"] for r in results] == ["a", "a~2"]
    labels = {"a": "supported", "a~2": "supported"}
    assert jd.agreement(labels, results)["judge_flags_what_hand_calls_supported"] == 1


# --- judging only the sentences that make claims (D-082) -----------------------------------------

PASSAGES = ["Drain cleaning, one fixture: $149 (starting price)."]


def test_conversation_sentences_are_left_out_and_claims_are_kept() -> None:
    answer = (
        "Thanks for your message. Drain cleaning for one fixture starts at $149.\n\n"
        "Platinum customers get priority forever. A member of our team will follow up."
    )
    kept = jd.claims_only(answer, PASSAGES, "How much for a drain?")
    assert kept == (
        "Drain cleaning for one fixture starts at $149. Platinum customers get priority forever."
    )


def test_a_request_for_a_known_detail_and_sympathy_are_not_claims() -> None:
    answer = "We're sorry to hear that. Drain cleaning starts at $149."
    kept = jd.claims_only(answer, PASSAGES, "My sink in Wren Common drains slowly.")
    assert kept == "Drain cleaning starts at $149."


def test_a_sentence_that_repeats_the_customers_message_is_not_a_claim() -> None:
    answer = "You asked about the slow kitchen sink in Wren Common. Drain cleaning starts at $149."
    kept = jd.claims_only(answer, PASSAGES, "my slow kitchen sink in Wren Common")
    assert kept == "Drain cleaning starts at $149."


def test_a_draft_with_nothing_but_conversation_has_no_claims() -> None:
    assert jd.claims_only("A member of our team will follow up.", PASSAGES, "q") == ""


def test_rejudging_skips_drafts_without_claims_and_calls_the_judge_for_the_rest() -> None:
    cases = [
        {
            "id": "a",
            "question": "q",
            "answer": "Drain cleaning starts at $149.",
            "passages": PASSAGES,
        },
        {
            "id": "b",
            "question": "q",
            "answer": "A member of our team will follow up.",
            "passages": [],
        },
        {"id": "c", "question": "q", "answer": "Free pipes for life.", "passages": PASSAGES},
    ]
    judge = ScriptedJudge({"Free pipes": "unsupported"})
    results = jd.rejudge_claims(judge, cases, labelled={"a", "b"})
    assert [r["id"] for r in results] == ["a", "b"]  # only the labelled ones
    assert results[1]["verdict"] == "supported" and results[1]["note"] == "no claims"
    assert len(judge.calls) == 1 and judge.calls[0]["answer"] == "Drain cleaning starts at $149."


def test_the_two_agreement_figures_are_computed_on_the_same_drafts() -> None:
    labels = {"a": "supported", "b": "supported"}
    before = [{"id": "a", "verdict": "unsupported"}, {"id": "b", "verdict": "supported"}]
    after = [{"id": "a", "verdict": "supported"}, {"id": "b", "verdict": "supported"}]
    result = jd.compare_agreement(labels, before, after)
    assert result["whole_draft"]["exact"] == 1 and result["claims_only"]["exact"] == 2


# --- the damage check with the claims-only rule and real good drafts (D-082) -------------------


def test_the_good_drafts_are_the_ones_a_person_called_supported() -> None:
    cases = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
    labels = {"a": "supported", "b": "partly_supported", "c": ""}
    assert [c["id"] for c in jd.good_by_label(cases, labels)] == ["a"]


def test_claims_only_cases_keep_their_other_fields_and_drop_conversation() -> None:
    cases = [
        {
            "id": "a",
            "question": "q",
            "answer": "Thanks for your message. Drain cleaning starts at $149.",
            "passages": PASSAGES,
            "damage": "x",
        }
    ]
    out = jd.as_claims_only(cases)
    assert out[0]["answer"] == "Drain cleaning starts at $149." and out[0]["damage"] == "x"
    assert cases[0]["answer"].startswith("Thanks")  # the input is not changed
