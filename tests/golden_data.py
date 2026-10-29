"""The golden file as the tests may read it: the tuned split only.

The held-out items are run once, by the evaluation, before anything is tuned on them. A test that
ran a detector or a rule over them would be a tuning signal, so the suite never reads them: every
test that checks behaviour against labels loads the file through `tuned_golden()`. Tests of the
file's own structure (its schema, its counts, that no label leaks) may read all of it.
"""

import json
from pathlib import Path
from typing import Any

GOLDEN_FILE = Path(__file__).resolve().parent.parent / "eval/golden/citedesk_v1.json"


def load_golden() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(GOLDEN_FILE.read_text("utf-8"))
    return data


def tuned_golden() -> dict[str, Any]:
    """The golden file with the held-out items removed."""
    data = load_golden()
    return {**data, "items": [i for i in data["items"] if i["split"] == "tuned"]}
