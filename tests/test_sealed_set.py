"""The sealed set's commands: build and validate from a git-ignored folder, seal by hash.

These tests use invented items written here. They never read the real sealed set.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from tests.test_golden import DOCS, make_item
from tools import golden


def write_src(folder: Path, items: list[dict[str, Any]]) -> Path:
    src = folder / "src"
    src.mkdir(parents=True)
    (src / "a.json").write_text(json.dumps(items), encoding="utf-8")
    return src


def test_a_sealed_set_builds_from_sealed_items(tmp_path: Path) -> None:
    src = write_src(tmp_path, [make_item(id="s-one", split="sealed")])
    data, problems = golden.build_sealed(src, DOCS)
    assert problems == []
    assert data["header"]["name"] == golden.SEALED_NAME
    assert data["header"]["counts"]["by_split"] == {"sealed": 1}


def test_an_item_from_another_split_is_refused(tmp_path: Path) -> None:
    src = write_src(tmp_path, [make_item(id="s-one", split="sealed"), make_item(id="t-one")])
    _, problems = golden.build_sealed(src, DOCS)
    assert any("t-one" in p and "sealed" in p for p in problems)


def test_a_sealed_item_in_the_main_golden_file_is_refused() -> None:
    data = golden.build_golden(Path("."), DOCS, name="x", version=1, written_by="y")
    data["items"] = [make_item(id="s-one", split="sealed")]
    data["header"]["counts"] = {"items": 1, "by_split": {"sealed": 1}}
    assert any("sealed" in p for p in golden.validate_data(data, DOCS))


def test_an_invalid_sealed_item_is_reported_by_id(tmp_path: Path) -> None:
    bad = make_item(id="s-bad", split="sealed", sender_email="someone@" + "gmail.com")
    src = write_src(tmp_path, [bad])
    _, problems = golden.build_sealed(src, DOCS)
    assert any("s-bad" in p for p in problems)


def test_sealing_records_the_hash_once(tmp_path: Path) -> None:
    sealed = tmp_path / "sealed.json"
    sealed.write_text('{"items": []}\n', encoding="utf-8")
    hash_file = tmp_path / "sealed.sha256"
    golden.seal(sealed, hash_file)
    assert hash_file.read_text(encoding="utf-8").strip() == golden.file_hash(sealed)
    with pytest.raises(FileExistsError):
        golden.seal(sealed, hash_file)


def test_verify_detects_a_changed_file(tmp_path: Path) -> None:
    sealed = tmp_path / "sealed.json"
    sealed.write_text('{"items": []}\n', encoding="utf-8")
    hash_file = tmp_path / "sealed.sha256"
    golden.seal(sealed, hash_file)
    assert golden.verify_sealed(sealed, hash_file) is True
    sealed.write_text('{"items": [1]}\n', encoding="utf-8")
    assert golden.verify_sealed(sealed, hash_file) is False


def test_verify_is_false_when_either_file_is_missing(tmp_path: Path) -> None:
    assert golden.verify_sealed(tmp_path / "none.json", tmp_path / "none.sha256") is False


def test_the_sealed_summary_prints_counts_and_never_text(tmp_path: Path) -> None:
    item = make_item(id="s-one", split="sealed", body="A distinctive sentence about a leak.")
    data, _ = golden.build_sealed(write_src(tmp_path, [item]), DOCS)
    summary = golden.sealed_summary(data)
    assert "1 items" in summary
    assert "distinctive" not in summary
    assert "s-one" not in summary
