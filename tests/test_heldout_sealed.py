"""The held-out split stays sealed (docs/DECISIONS.md D-061).

The held-out items are run once, by the evaluation, before anything is tuned on them. A test that
ran a detector, a rule or a stage over them would be a tuning signal. Tests that check behaviour
against labels load the file through `tests.golden_data.tuned_golden`. The few tests below may read
the whole file because they check its structure, that no label leaks into the inbox or the
prompts, that labels agree with the routing rules, or filter to the tuned split themselves.
"""

from pathlib import Path

from tests.golden_data import load_golden, tuned_golden

TESTS = Path(__file__).resolve().parent

MAY_READ_THE_WHOLE_FILE = {
    "test_golden.py",  # the file's schema and counts
    "test_import_inquiries.py",  # no label or note leaks into an inbox record
    "test_repo_hygiene.py",  # the file is committed
    "test_routing_golden.py",  # labels agree with the routing rules (no system output)
    "test_drafting.py",  # no golden message is copied into the draft prompt
    "test_understand.py",  # no golden message is copied into the understand prompt
    "test_run_pipeline.py",  # filters to the tuned split itself
    "test_score_understanding.py",  # filters to the tuned split itself
    "test_heldout_sealed.py",  # this file
}


def test_only_structure_tests_read_the_whole_golden_file() -> None:
    readers = {
        path.name
        for path in TESTS.glob("test_*.py")
        if "citedesk_v1.json" in path.read_text("utf-8")
    }
    assert readers <= MAY_READ_THE_WHOLE_FILE, (
        f"{sorted(readers - MAY_READ_THE_WHOLE_FILE)} read the held-out items: load the golden "
        "file with tests.golden_data.tuned_golden() instead"
    )


def test_tuned_golden_holds_no_held_out_item() -> None:
    assert {i["split"] for i in tuned_golden()["items"]} == {"tuned"}


def test_the_held_out_split_exists_and_is_about_a_third() -> None:
    items = load_golden()["items"]
    held = sum(i["split"] == "heldout" for i in items)
    assert 0.30 <= held / len(items) <= 0.40


def test_no_test_names_the_sealed_file_or_its_folder() -> None:
    """The sealed set is read only by the runner, once (D-071): a test that opened it would be a
    tuning signal. Tests refer to it through the constants in tools/golden.py."""
    named = {
        path.name
        for path in TESTS.glob("test_*.py")
        if path.name != "test_heldout_sealed.py"
        and (
            "citedesk_sealed_v1" in path.read_text("utf-8")
            or "data/sealed" in path.read_text("utf-8")
        )
    }
    assert not named, f"{sorted(named)} name the sealed file"
