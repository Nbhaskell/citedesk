"""The golden set: models, validation, build and report.

Run:
    python -m tools.golden build      merge eval/golden/src/*.json into eval/golden/citedesk_v1.json
    python -m tools.golden validate   check the committed file: schema, rules, docs, anchors
    python -m tools.golden report     counts per intent, category, route and reason
    python -m tools.golden schema     write eval/golden/golden.schema.json
    build, validate and report take --set kestrel (the default) or --set fernhollow, the
    invented electrician's set in eval/golden-electrical/ (D-099)
    python -m tools.golden build-sealed | validate-sealed | seal | verify-sealed
                                      the sealed set in data/sealed/ (D-071); prints counts only

Names and values come from citedesk/models.py, which tests keep in step with
docs/BACKEND_SCHEMA.md and the database CHECK constraints. The required-fields table is
citedesk/routing.py's, so there is one copy of it (D-040).
"""

import hashlib
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from citedesk import models
from citedesk.routing import missing_fields
from citedesk.trade import ELECTRICAL, PLUMBING, Trade

REPO_ROOT = Path(__file__).resolve().parent.parent
GOLDEN_DIR = REPO_ROOT / "eval/golden"
SRC_DIR = GOLDEN_DIR / "src"
GOLDEN_FILE = GOLDEN_DIR / "citedesk_v1.json"
SCHEMA_FILE = GOLDEN_DIR / "golden.schema.json"
DOCS_DIR = REPO_ROOT / "universe/docs"

# The sealed set (D-071) lives in a git-ignored folder; only the hash of its built file is
# committed.
SEALED_DIR = REPO_ROOT / "data/sealed"
SEALED_SRC_DIR = SEALED_DIR / "src"
SEALED_FILE = SEALED_DIR / "citedesk_sealed_v1.json"
SEALED_HASH_FILE = GOLDEN_DIR / "citedesk_sealed.sha256"
SEALED_NAME = "citedesk_sealed_v1"
MAIN_SPLITS = ("tuned", "heldout")

NAME = "citedesk_v1"
VERSION = 1
REFERENCE_DATE = "2026-10-28"
WRITTEN_BY = (
    "An AI model (Claude), working from the same fact sheet and documents the system uses. "
    "Not blind: written by the same process that wrote the knowledge base."
)

CATEGORIES = (
    "routine_answerable",
    "multi_intent",
    "vague_missing_details",
    "booking_flow",
    "urgent",
    "safety",
    "angry_complaint",
    "dispute_legal",
    "policy_exception",
    "billing",
    "partnership_sales",
    "spam",
    "out_of_scope",
    "follow_up",
    "injection",
    "unanswerable",
    "near_miss",
    "edge",
)


@dataclass(frozen=True)
class GoldenSet:
    """One labelled set: where its items and documents are, which splits it may hold, and
    the trade whose service types its labels may use (D-099)."""

    key: str
    name: str
    src_dir: Path
    golden_file: Path
    docs_dir: Path
    written_by: str
    splits: tuple[str, ...]
    trade: Trade


ELECTRICAL_DIR = REPO_ROOT / "eval/golden-electrical"
SETS: dict[str, GoldenSet] = {
    "kestrel": GoldenSet(
        key="kestrel",
        name=NAME,
        src_dir=SRC_DIR,
        golden_file=GOLDEN_FILE,
        docs_dir=DOCS_DIR,
        written_by=WRITTEN_BY,
        splits=MAIN_SPLITS,
        trade=PLUMBING,
    ),
    # The invented electrician's set is a test of the unchanged system on another trade. It is
    # never used for tuning, so it holds held-out items only.
    "fernhollow": GoldenSet(
        key="fernhollow",
        name="fernhollow_v1",
        src_dir=ELECTRICAL_DIR / "src",
        golden_file=ELECTRICAL_DIR / "fernhollow_v1.json",
        docs_dir=REPO_ROOT / "universe-electrical/docs",
        written_by=(
            "An AI model (Claude), in a session that was given the labelling rules and the "
            "electrician's fact sheet and documents, and not the prompts, code or results."
        ),
        splits=("heldout",),
        trade=ELECTRICAL,
    ),
}

NOT_IN_KB = "NOT_IN_KNOWLEDGE_BASE"
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE_RE = re.compile(r"\b(\d{3})[-. ](\d{4})\b")
ISO_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


ENUMS = {
    "channel": models.Channel,
    "intent": models.Intent,
    "urgency": models.Urgency,
    "route": models.Route,
    "reason_code": models.ReasonCode,
    "service_type": models.ServiceType,
    "property_type": models.PropertyType,
}


def schema_enum(name: str) -> tuple[str, ...]:
    """The values of a schema enumeration, in the order of docs/BACKEND_SCHEMA.md section 1."""
    return tuple(member.value for member in ENUMS[name])


Intent = Literal[schema_enum("intent")]  # type: ignore[valid-type]
Urgency = Literal[schema_enum("urgency")]  # type: ignore[valid-type]
Route = Literal[schema_enum("route")]  # type: ignore[valid-type]
ReasonCode = Literal[schema_enum("reason_code")]  # type: ignore[valid-type]
Channel = Literal[schema_enum("channel")]  # type: ignore[valid-type]
ServiceType = Literal[schema_enum("service_type")]  # type: ignore[valid-type]
PropertyType = Literal[schema_enum("property_type")]  # type: ignore[valid-type]
Category = Literal[CATEGORIES]  # type: ignore[valid-type]
Split = Literal["tuned", "heldout", "sealed"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Evidence(Strict):
    file: str
    anchor: str = Field(min_length=1)


class Fields(Strict):
    """Every core key is present; null means the customer did not say."""

    service_type: ServiceType | None
    start_date: str | None
    property_type: PropertyType | None
    address_area: str | None
    booking_reference: str | None = None

    @field_validator("start_date")
    @classmethod
    def iso_date(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not ISO_DATE_RE.fullmatch(value):
            raise ValueError("start_date must be YYYY-MM-DD or null")
        date.fromisoformat(value)
        return value


class Labels(Strict):
    intents: list[Intent] = Field(min_length=1)
    primary_intent: Intent
    urgency: Urgency
    fields: Fields
    should_escalate: bool
    expected_reason_codes: list[ReasonCode]
    expected_route: Route
    answerable_from_docs: bool
    contains_sensitive_data: bool = False

    @field_validator("intents", "expected_reason_codes")
    @classmethod
    def unique(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("values must not repeat")
        return value


class Item(Strict):
    id: Annotated[str, Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")]
    split: Split
    category: Category
    channel: Channel
    sender_name: str = Field(min_length=1)
    sender_email: str | None = None
    subject: str | None = None
    body: str = Field(min_length=1)
    labels: Labels
    evidence: list[Evidence] = []
    notes: str | None = None


class Header(Strict):
    name: str
    version: int
    reference_date: str
    written_by: str
    docs_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    counts: dict[str, Any]


class GoldenFile(Strict):
    header: Header
    items: list[Item]


# --- rules in plain code ---------------------------------------------------------------------


def derive_route(
    intents: list[str], primary: str, reasons: list[str], fields: dict[str, Any]
) -> str:
    """Docs/TRD.md section 4.3, applied to the labels. A knowledge-base decline can only be
    recorded on the draft path, so it counts only when nothing else already decided the route."""
    other_reasons = [r for r in reasons if r != NOT_IN_KB]
    if primary == "spam" and intents == ["spam"]:
        return "archive"
    if other_reasons:
        return "escalate"
    if missing_fields(intents, fields):
        return "request_details"
    if NOT_IN_KB in reasons:
        return "escalate"
    return "draft_reply"


def normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def load_docs(directory: Path = DOCS_DIR) -> dict[str, str]:
    return {p.name: p.read_text("utf-8") for p in sorted(directory.glob("*.md"))}


def docs_sha256(docs: dict[str, str]) -> str:
    digest = hashlib.sha256()
    for name in sorted(docs):
        digest.update(name.encode("utf-8") + b"\0" + docs[name].encode("utf-8") + b"\0")
    return digest.hexdigest()


# --- validation ------------------------------------------------------------------------------


def format_errors(error: ValidationError, prefix: str) -> list[str]:
    return [f"{prefix}: {'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in error.errors()]


def synthetic_problems(item: Item) -> list[str]:
    found: list[str] = []
    for label, text in (
        ("sender_email", item.sender_email or ""),
        ("subject", item.subject or ""),
        ("body", item.body),
    ):
        for email in EMAIL_RE.findall(text):
            if not email.lower().endswith("@example.com"):
                found.append(f"{label} has email {email!r}, which is not at example.com")
        for exchange, line in PHONE_RE.findall(text):
            if not (exchange == "555" and line.startswith("01")):
                found.append(
                    f"{label} has phone number {exchange}-{line}, not in the 555-01xx range"
                )
    return found


def validate_item(raw: dict[str, Any], docs: dict[str, str], trade: Trade = PLUMBING) -> list[str]:
    item_id = str(raw.get("id", "?")) if isinstance(raw, dict) else "?"
    try:
        item = Item.model_validate(raw)
    except ValidationError as error:
        return format_errors(error, item_id)

    found: list[str] = []
    lab = item.labels
    fields = lab.fields.model_dump()
    intents, reasons = list(lab.intents), list(lab.expected_reason_codes)

    if lab.primary_intent not in intents:
        found.append("primary_intent must be one of intents")
    service = fields.get("service_type")
    if service is not None and service not in {m.value for m in trade.service_types}:
        found.append(f"service_type {service!r} is not a service type of the {trade.key} trade")

    derived = derive_route(intents, lab.primary_intent, reasons, fields)
    if lab.expected_route != derived:
        found.append(
            f"expected_route is {lab.expected_route!r} but the routing rules give {derived!r}"
        )
    if lab.should_escalate != (lab.expected_route == "escalate"):
        found.append("should_escalate must be true exactly when expected_route is 'escalate'")

    if "health_or_safety" in intents and "HEALTH_SAFETY" not in reasons:
        found.append("intent health_or_safety requires reason code HEALTH_SAFETY")
    if "complaint" in intents and "COMPLAINT" not in reasons:
        found.append("intent complaint requires reason code COMPLAINT")
    if fields.get("property_type") == "commercial" and "POLICY_EXCEPTION_REQUEST" not in reasons:
        found.append("property_type commercial requires reason code POLICY_EXCEPTION_REQUEST")
    if NOT_IN_KB in reasons and (
        any(r != NOT_IN_KB for r in reasons) or missing_fields(intents, fields)
    ):
        found.append(
            f"{NOT_IN_KB} is only recorded when the draft path is reached "
            "(no other reason and no missing details)"
        )

    if lab.answerable_from_docs and not item.evidence:
        found.append("answerable_from_docs is true but there is no evidence")
    if not lab.answerable_from_docs and item.evidence:
        found.append("answerable_from_docs is false but evidence is given")
    for ev in item.evidence:
        if ev.file not in docs:
            found.append(f"evidence file {ev.file!r} does not exist")
        elif normalise(ev.anchor) not in normalise(docs[ev.file]):
            found.append(f"evidence anchor {ev.anchor!r} not found in {ev.file}")

    found += synthetic_problems(item)
    return [f"{item_id}: {p}" for p in found]


def validate_data(
    data: dict[str, Any],
    docs: dict[str, str],
    allowed_splits: tuple[str, ...] = MAIN_SPLITS,
    trade: Trade = PLUMBING,
) -> list[str]:
    found: list[str] = []
    if not isinstance(data, dict) or "header" not in data or "items" not in data:
        return ["file must have 'header' and 'items'"]
    try:
        header = Header.model_validate(data["header"])
    except ValidationError as error:
        return format_errors(error, "header")
    try:
        date.fromisoformat(header.reference_date)
    except ValueError:
        found.append("header: reference_date must be an ISO date")
    if header.docs_sha256 != docs_sha256(docs):
        found.append(
            "header: the golden set was written against different documents than the current "
            "ones. Check the evidence anchors, then run: python -m tools.golden build"
        )
    if header.counts.get("items") != len(data["items"]):
        found.append("header: counts.items does not match the number of items")

    seen: Counter[str] = Counter(str(i.get("id")) for i in data["items"] if isinstance(i, dict))
    found += [f"duplicate id {i!r}" for i, n in sorted(seen.items()) if n > 1]
    for raw in data["items"]:
        if isinstance(raw, dict) and raw.get("split") not in allowed_splits:
            found.append(
                f"{raw.get('id', '?')}: split {raw.get('split')!r} is not allowed in this file "
                f"(it takes only: {', '.join(allowed_splits)})"
            )
        found += validate_item(raw, docs, trade)
    return found


# --- build and report ------------------------------------------------------------------------


def build_golden(
    src_dir: Path,
    docs: dict[str, str],
    *,
    name: str,
    version: int,
    written_by: str,
    reference_date: str = REFERENCE_DATE,
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for path in sorted(src_dir.glob("*.json")):
        items += json.loads(path.read_text("utf-8"))
    items.sort(key=lambda i: str(i.get("id")))
    splits = Counter(str(i.get("split")) for i in items)
    return {
        "header": {
            "name": name,
            "version": version,
            "reference_date": reference_date,
            "written_by": written_by,
            "docs_sha256": docs_sha256(docs),
            "counts": {"items": len(items), "by_split": dict(sorted(splits.items()))},
        },
        "items": items,
    }


def build_golden_items(
    items: list[dict[str, Any]], docs: dict[str, str], target: GoldenSet
) -> dict[str, Any]:
    """A golden file for a named set, from items already read."""
    ordered = sorted(items, key=lambda i: str(i.get("id")))
    splits = Counter(str(i.get("split")) for i in ordered)
    return {
        "header": {
            "name": target.name,
            "version": VERSION,
            "reference_date": REFERENCE_DATE,
            "written_by": target.written_by,
            "docs_sha256": docs_sha256(docs),
            "counts": {"items": len(ordered), "by_split": dict(sorted(splits.items()))},
        },
        "items": ordered,
    }


def table(title: str, counter: Counter[str], order: tuple[str, ...] | None = None) -> str:
    keys = list(order) if order else sorted(counter)
    rows = [f"  {k:<28}{counter.get(k, 0):>4}" for k in keys]
    return f"{title}\n" + "\n".join(rows)


def report(data: dict[str, Any]) -> str:
    items = data["items"]
    labels = [i["labels"] for i in items]
    splits = Counter(i["split"] for i in items)
    parts = [
        f"{len(items)} items ({', '.join(f'{k} {v}' for k, v in sorted(splits.items()))})",
        table(
            "Primary intent (every intent should appear)",
            Counter(lab["primary_intent"] for lab in labels),
            schema_enum("intent"),
        ),
        table("Category", Counter(i["category"] for i in items), CATEGORIES),
        table(
            "Expected route", Counter(lab["expected_route"] for lab in labels), schema_enum("route")
        ),
        table(
            "Escalation reason (an item can have several)",
            Counter(r for lab in labels for r in lab["expected_reason_codes"]),
            schema_enum("reason_code"),
        ),
        table("Urgency", Counter(lab["urgency"] for lab in labels), schema_enum("urgency")),
        table(
            "Answerable from the documents",
            Counter("yes" if lab["answerable_from_docs"] else "no" for lab in labels),
            ("yes", "no"),
        ),
    ]
    return "\n\n".join(parts)


# --- the sealed set (D-071) ------------------------------------------------------------------


def build_sealed(src_dir: Path, docs: dict[str, str]) -> tuple[dict[str, Any], list[str]]:
    """Merge the sealed items and validate them. Only items with split 'sealed' are accepted."""
    data = build_golden(src_dir, docs, name=SEALED_NAME, version=VERSION, written_by=WRITTEN_BY)
    return data, validate_data(data, docs, allowed_splits=("sealed",))


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def seal(sealed_file: Path, hash_file: Path) -> str:
    """Record the file's SHA-256 in the committed hash file. Refuses to overwrite a hash."""
    if hash_file.exists():
        raise FileExistsError(f"{hash_file.name} already exists; a sealed hash is never replaced")
    digest = file_hash(sealed_file)
    hash_file.write_text(digest + "\n", encoding="utf-8")
    return digest


def verify_sealed(sealed_file: Path, hash_file: Path) -> bool:
    """True when the file exists and its hash equals the committed one."""
    if not sealed_file.is_file() or not hash_file.is_file():
        return False
    return file_hash(sealed_file) == hash_file.read_text(encoding="utf-8").strip()


def sealed_summary(data: dict[str, Any]) -> str:
    """Counts only: no ids, no text, so nothing about any item is shown."""
    items = data["items"]
    labels = [i["labels"] for i in items]
    return "\n\n".join(
        [
            f"{len(items)} items",
            table("Category", Counter(i["category"] for i in items), CATEGORIES),
            table(
                "Primary intent",
                Counter(lab["primary_intent"] for lab in labels),
                schema_enum("intent"),
            ),
            table(
                "Expected route",
                Counter(lab["expected_route"] for lab in labels),
                schema_enum("route"),
            ),
            table(
                "Escalation reason",
                Counter(r for lab in labels for r in lab["expected_reason_codes"]),
                schema_enum("reason_code"),
            ),
        ]
    )


# --- command line ----------------------------------------------------------------------------


def write_json(path: Path, data: Any) -> None:
    path.write_bytes((json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))


def cmd_build(target: GoldenSet) -> int:
    docs = load_docs(target.docs_dir)
    items: list[dict[str, Any]] = []
    for path in sorted(target.src_dir.glob("*.json")):
        items += json.loads(path.read_text("utf-8"))
    data = build_golden_items(items, docs, target)
    problems = validate_data(data, docs, target.splits, target.trade)
    if problems:
        print(f"Not writing: {len(problems)} problem(s):")
        for p in problems:
            print(f"  - {p}")
        return 1
    write_json(target.golden_file, data)
    print(f"Wrote {target.golden_file.name}: {len(data['items'])} items")
    return 0


def cmd_validate(target: GoldenSet) -> int:
    docs = load_docs(target.docs_dir)
    data = json.loads(target.golden_file.read_text("utf-8"))
    problems = validate_data(data, docs, target.splits, target.trade)
    if problems:
        print(f"{len(problems)} problem(s):")
        for p in problems:
            print(f"  - {p}")
        return 1
    print(f"OK: {len(data['items'])} items are valid\n")
    print(report(data))
    return 0


def cmd_build_sealed() -> int:
    data, problems = build_sealed(SEALED_SRC_DIR, load_docs())
    if problems:
        print(f"Not writing: {len(problems)} problem(s):")
        for p in problems:
            print(f"  - {p}")
        return 1
    write_json(SEALED_FILE, data)
    print(f"Wrote {SEALED_FILE.relative_to(REPO_ROOT)}\n")
    print(sealed_summary(data))
    return 0


def cmd_validate_sealed() -> int:
    data = json.loads(SEALED_FILE.read_text("utf-8"))
    problems = validate_data(data, load_docs(), allowed_splits=("sealed",))
    if problems:
        print(f"{len(problems)} problem(s):")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("OK\n")
    print(sealed_summary(data))
    return 0


def main(argv: list[str]) -> int:
    command = argv[1] if len(argv) > 1 else ""
    if command == "build-sealed":
        return cmd_build_sealed()
    if command == "validate-sealed":
        return cmd_validate_sealed()
    if command == "seal":
        print(f"Sealed: {seal(SEALED_FILE, SEALED_HASH_FILE)}")
        return 0
    if command == "verify-sealed":
        ok = verify_sealed(SEALED_FILE, SEALED_HASH_FILE)
        print("The sealed file matches the committed hash." if ok else "MISMATCH or missing file.")
        return 0 if ok else 1
    key = argv[argv.index("--set") + 1] if "--set" in argv[2:-1] else "kestrel"
    target = SETS.get(key)
    if command in ("build", "validate", "report") and target is None:
        print(f"Unknown set {key!r}; known: {', '.join(sorted(SETS))}")
        return 2
    if command == "build" and target is not None:
        return cmd_build(target)
    if command == "validate" and target is not None:
        return cmd_validate(target)
    if command == "report" and target is not None:
        print(report(json.loads(target.golden_file.read_text("utf-8"))))
        return 0
    if command == "schema":
        write_json(SCHEMA_FILE, GoldenFile.model_json_schema())
        print(f"Wrote {SCHEMA_FILE.relative_to(REPO_ROOT)}")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
