"""The blind intent-labelling sheet and its agreement scorer (tools/label_agreement.py).

All items here are invented fixtures built in the tests. No test reads the real golden set.
"""

import json
from pathlib import Path

import pytest

from tools import label_agreement as la


def item(
    item_id: str,
    primary: str = "service_question",
    split: str = "tuned",
    body: str | None = None,
) -> dict:
    return {
        "id": item_id,
        "split": split,
        "category": f"cat-{item_id}",
        "channel": "email",
        "sender_name": "Pat Example",
        "subject": "A question about the visit",
        "body": body or "Please tell me when you can come.",
        "labels": {"primary_intent": primary, "intents": [primary]},
        "notes": f"note-{item_id}",
    }


def pool() -> list[dict]:
    tuned = [item(f"t{i}", split="tuned") for i in range(6)]
    held = [item(f"h{i}", split="heldout") for i in range(4)]
    return tuned + held


# --- choosing the items ---


def test_selection_is_repeatable_and_depends_on_the_seed() -> None:
    def ids(seed: int) -> list[str]:
        return [i["id"] for i in la.select_items(pool(), n=5, seed=seed)]

    assert ids(1) == ids(1)
    assert len({tuple(ids(s)) for s in range(10)}) > 1


def test_selection_keeps_the_mix_of_splits() -> None:
    chosen = la.select_items(pool(), n=5, seed=3)
    splits = [i["split"] for i in chosen]
    assert len(chosen) == 5
    assert splits.count("tuned") == 3
    assert splits.count("heldout") == 2


def test_selection_larger_than_the_pool_returns_every_item_once() -> None:
    chosen = la.select_items(pool(), n=99, seed=0)
    assert sorted(i["id"] for i in chosen) == sorted(i["id"] for i in pool())


def test_a_sealed_item_is_refused() -> None:
    with pytest.raises(ValueError, match="sealed"):
        la.select_items([*pool(), item("s1", split="sealed")], n=3, seed=0)


# --- the sheet ---


def test_the_sheet_shows_the_message_and_hides_every_label() -> None:
    chosen = [item("billing-fee-marker", body="Why is there a fee on my bill?")]
    chosen[0]["category"] = "billing"
    text, order = la.build_sheet(chosen)
    assert order == ["billing-fee-marker"]
    assert "Why is there a fee on my bill?" in text
    assert "A question about the visit" in text
    assert "billing-fee-marker" not in text  # the id can hint at the label
    assert "note-billing-fee-marker" not in text
    assert "cat-" not in text
    assert "Pat Example" not in text


def test_the_sheet_numbers_items_from_one_in_order() -> None:
    text, order = la.build_sheet([item("a"), item("b"), item("c")])
    assert order == ["a", "b", "c"]
    assert text.index("## 1.") < text.index("## 2.") < text.index("## 3.")


def test_the_sheet_lists_every_intent_once_in_the_rules() -> None:
    text, _ = la.build_sheet([item("a")])
    for intent in la.INTENTS:
        assert f"`{intent}`" in text


# --- the labels file ---


def test_the_template_is_keyed_by_number_and_carries_the_sheet_id() -> None:
    order = ["a", "b", "c"]
    template = la.label_template(order)
    assert template["labels"] == {"1": "", "2": "", "3": ""}
    assert template["unsure"] == []
    assert template["sheet_id"] == la.sheet_id(order)
    assert la.sheet_id(["a", "b", "c"]) != la.sheet_id(["a", "c", "b"])


# --- scoring ---


def make_labels(order: list[str], values: list[str], **extra: object) -> dict:
    template = la.label_template(order)
    template["labeller"] = "reviewer 2"
    template["labels"] = {str(i + 1): v for i, v in enumerate(values)}
    template.update(extra)
    return template


def golden_for(*pairs: tuple[str, str]) -> dict[str, dict]:
    return {i: item(i, primary=p) for i, p in pairs}


def test_agreement_counts_exact_matches_and_lists_the_disagreements() -> None:
    gold = golden_for(("a", "spam"), ("b", "other"), ("c", "complaint"), ("d", "spam"))
    order = ["a", "b", "c", "d"]
    labels = make_labels(order, ["spam", "billing_question", "complaint", "spam"])
    result = la.score(gold, order, labels)
    assert result["agreement"]["n"] == 4
    assert result["agreement"]["exact"] == 3
    assert result["disagreements"] == [
        {"id": "b", "original": "other", "new": "billing_question", "unsure": False}
    ]
    assert result["confusion"] == {"other -> billing_question": 1}
    assert 0 < result["agreement"]["kappa"] < 1


def test_blank_and_invalid_labels_are_set_aside_not_counted() -> None:
    gold = golden_for(("a", "spam"), ("b", "other"), ("c", "complaint"))
    order = ["a", "b", "c"]
    labels = make_labels(order, ["spam", "", "complain"])
    result = la.score(gold, order, labels)
    assert result["agreement"]["n"] == 1
    assert result["unlabelled"] == 1
    assert result["invalid"] == [{"number": "3", "value": "complain"}]


def test_a_labels_file_from_another_sheet_is_refused() -> None:
    gold = golden_for(("a", "spam"), ("b", "other"))
    labels = make_labels(["a", "b"], ["spam", "other"])
    with pytest.raises(ValueError, match="sheet"):
        la.score(gold, ["b", "a"], labels)


def test_unsure_items_are_reported_apart() -> None:
    gold = golden_for(("a", "spam"), ("b", "other"), ("c", "complaint"), ("d", "spam"))
    order = ["a", "b", "c", "d"]
    labels = make_labels(
        order, ["spam", "billing_question", "complaint", "other"], unsure=["2", "4"]
    )
    result = la.score(gold, order, labels)
    assert result["unsure"] == {"n": 2, "exact": 0, "sure_n": 2, "sure_exact": 2}
    assert [d["unsure"] for d in result["disagreements"]] == [True, True]


def test_no_kappa_without_labels() -> None:
    gold = golden_for(("a", "spam"))
    result = la.score(gold, ["a"], make_labels(["a"], [""]))
    assert result["agreement"]["n"] == 0
    assert result["agreement"]["kappa"] is None


def test_model_comparison_separates_label_doubt_from_model_error() -> None:
    gold = golden_for(
        ("a", "spam"),  # model right, labeller right
        ("b", "other"),  # model wrong; labeller sides with the model: doubt about the label
        ("c", "complaint"),  # model wrong; labeller sides with the original: model error
        ("d", "pricing_question"),  # model wrong; labeller agrees with neither
        ("e", "spam"),  # not in the run: left out of the comparison
    )
    order = ["a", "b", "c", "d", "e"]
    labels = make_labels(
        order, ["spam", "billing_question", "complaint", "service_question", "spam"]
    )
    run = {"a": "spam", "b": "billing_question", "c": "other", "d": "billing_question"}
    result = la.score(gold, order, labels, model=run)
    assert result["model"] == {
        "n": 4,
        "vs_original": 1,
        "vs_new": 2,
        "wrong_vs_original": 3,
        "new_agrees_with_model": 1,
        "new_agrees_with_original": 1,
        "new_agrees_with_neither": 1,
        "agreed_n": 2,  # a and c: both labellers agree
        "agreed_right": 1,  # the model is right on a only
    }


def test_the_run_reader_keeps_only_items_the_model_read(tmp_path: Path) -> None:
    path = tmp_path / "run.json"
    path.write_text(
        json.dumps(
            {
                "items": [
                    {"id": "a", "primary_intent": "spam", "classified": True},
                    {"id": "b", "primary_intent": None, "classified": False},
                    {"id": "c", "classified": True},
                ]
            }
        ),
        encoding="utf-8",
    )
    assert la.load_run_intents(path) == {"a": "spam"}


# --- the report ---


def test_the_report_holds_ids_and_labels_but_no_message_text() -> None:
    marker = "UNIQUE-MESSAGE-WORDS-12345"
    gold = {
        "a": item("a", primary="spam", body=marker),
        "b": item("b", primary="other", body=marker),
    }
    order = ["a", "b"]
    labels = make_labels(order, ["spam", "billing_question"])
    text = la.render(la.score(gold, order, labels))
    assert marker not in text
    assert "other -> billing_question" in text
    assert "reviewer 2" in text


# --- the command line ---


def write_golden(path: Path, items: list[dict]) -> None:
    path.write_text(json.dumps({"header": {}, "items": items}), encoding="utf-8")


def test_sheet_command_writes_sheet_order_and_template(tmp_path: Path) -> None:
    golden = tmp_path / "golden.json"
    write_golden(golden, pool())
    labels = tmp_path / "labels.json"
    code = la.main(
        ["sheet", "--golden", str(golden), "--n", "4", "--seed", "2",
         "--out-dir", str(tmp_path), "--labels-file", str(labels)]
    )  # fmt: skip
    assert code == 0
    order = json.loads((tmp_path / "intent-labelling-sheet.order.json").read_text(encoding="utf-8"))
    assert len(order) == 4
    sheet = (tmp_path / "intent-labelling-sheet.md").read_text(encoding="utf-8")
    assert all(i not in sheet for i in order)
    template = json.loads(labels.read_text(encoding="utf-8"))
    assert template["sheet_id"] == la.sheet_id(order)


def test_sheet_command_does_not_overwrite_written_labels(tmp_path: Path) -> None:
    golden = tmp_path / "golden.json"
    write_golden(golden, pool())
    labels = tmp_path / "labels.json"
    labels.write_text('{"labeller": "x", "labels": {"1": "spam"}}', encoding="utf-8")
    code = la.main(
        ["sheet", "--golden", str(golden), "--n", "4", "--seed", "2",
         "--out-dir", str(tmp_path), "--labels-file", str(labels)]
    )  # fmt: skip
    assert code != 0
    assert json.loads(labels.read_text(encoding="utf-8"))["labels"] == {"1": "spam"}


def test_score_command_end_to_end(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    items = pool()
    golden = tmp_path / "golden.json"
    write_golden(golden, items)
    labels = tmp_path / "labels.json"
    la.main(
        ["sheet", "--golden", str(golden), "--n", "4", "--seed", "2",
         "--out-dir", str(tmp_path), "--labels-file", str(labels)]
    )  # fmt: skip
    order = json.loads((tmp_path / "intent-labelling-sheet.order.json").read_text(encoding="utf-8"))
    data = json.loads(labels.read_text(encoding="utf-8"))
    data["labeller"] = "reviewer 2"
    data["labels"] = {str(i + 1): "service_question" for i in range(len(order))}
    labels.write_text(json.dumps(data), encoding="utf-8")
    report = tmp_path / "report.md"
    code = la.main(
        ["score", "--golden", str(golden), "--labels-file", str(labels),
         "--order", str(tmp_path / "intent-labelling-sheet.order.json"), "--md", str(report)]
    )  # fmt: skip
    assert code == 0
    assert "Exact agreement: 4 of 4" in report.read_text(encoding="utf-8")
