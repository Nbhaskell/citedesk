"""Fail if any document disagrees with universe/facts.json.

Run: python -m tools.check_consistency

Checks, in both directions where it makes sense (nothing invented, nothing dropped):
money amounts, times, dates, percentages, phone numbers, emails, other numbers, and a list of
names and phrases that must appear in a named document.
"""

import json
import re
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
UNIVERSE = REPO_ROOT / "universe"

MONEY_KEYS = {"price", "price_per_hour", "travel_fee", "late_fee", "written_estimate_required_over"}

MONEY_RE = re.compile(r"\$\d{1,3}(?:,\d{3})+|\$\d+(?:\.\d{2})?")
PERCENT_RE = re.compile(r"\d+(?:\.\d+)?%")
TIME_RE = re.compile(r"\b(\d{1,2}):(\d{2}) (am|pm)\b")
NOON_RE = re.compile(r"\bnoon\b")
MONTHS = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]
DATE_RE = re.compile(rf"\b({'|'.join(MONTHS)}) (\d{{1,2}}), (\d{{4}})\b")
PHONE_RE = re.compile(r"\b555-\d{4}\b")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
NUMBER_RE = re.compile(r"\d+")


def money(amount: float) -> str:
    return f"${int(amount):,}"


def percent(value: float) -> str:
    return f"{round(value, 6):g}%"


def walk(node: Any, key: str = "") -> Iterator[tuple[str, Any]]:
    yield key, node
    if isinstance(node, dict):
        for k, v in node.items():
            yield from walk(v, k)
    elif isinstance(node, list):
        for item in node:
            yield from walk(item, key)


def facts_money(facts: dict[str, Any]) -> set[str]:
    return {
        money(v)
        for k, v in walk(facts)
        if k in MONEY_KEYS and isinstance(v, int | float) and not isinstance(v, bool)
    }


def facts_percents(facts: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    for k, v in walk(facts):
        if not isinstance(v, int | float) or isinstance(v, bool):
            continue
        if k == "parts_sales_tax_rate":
            out.add(percent(v * 100))
        elif "percent" in k:
            out.add(percent(v))
    return out


def facts_text(facts: dict[str, Any]) -> str:
    return json.dumps(facts, ensure_ascii=False)


def doc_times(text: str) -> set[str]:
    found: set[str] = set()
    for h, m, suffix in TIME_RE.findall(text):
        hour = int(h) % 12 + (12 if suffix == "pm" else 0)
        found.add(f"{hour:02d}:{m}")
    if NOON_RE.search(text):
        found.add("12:00")
    return found


def doc_dates(text: str) -> dict[str, str]:
    """Map ISO date to the text as written."""
    out: dict[str, str] = {}
    for month, day, year in DATE_RE.findall(text):
        iso = f"{year}-{MONTHS.index(month) + 1:02d}-{int(day):02d}"
        out[iso] = f"{month} {day}, {year}"
    return out


def strip_handled(text: str) -> str:
    for pattern in (EMAIL_RE, PHONE_RE, MONEY_RE, PERCENT_RE, DATE_RE, TIME_RE, NOON_RE):
        text = pattern.sub(" ", text)
    return text


def required_phrases(facts: dict[str, Any]) -> list[tuple[str, str]]:
    """(document, text that must appear in it)."""
    out: list[tuple[str, str]] = []
    out += [("services.md", s["name"]) for s in facts["services_offered"]]
    out += [("pricing.md", j["job"]) for j in facts["pricing"]["flat_price_jobs"]]
    out += [("pricing.md", q) for q in facts["pricing"]["quote_only"]]
    out += [("policies.md", n) for n in facts["policies"]["not_offered"]]
    area = facts["service_area"]
    out += [("service-area.md", a) for a in area["core"] + area["outer"]["areas"]]
    out += [("hours.md", d["name"]) for d in facts["hours"]["closed_dates"]]
    out += [("about.md", s["name"]) for s in facts["staff"]]
    return out


def check(facts: dict[str, Any], docs: dict[str, str]) -> list[str]:
    problems: list[str] = []
    all_text = "\n".join(docs.values())
    fact_blob = facts_text(facts)

    # Money: every amount in a document is a fact, and every fact appears somewhere.
    allowed_money = facts_money(facts)
    for name, text in sorted(docs.items()):
        for amount in sorted(set(MONEY_RE.findall(text))):
            if amount not in allowed_money:
                problems.append(f"{name}: price {amount} is not in the fact sheet")
    present_money = set(MONEY_RE.findall(all_text))
    for amount in sorted(allowed_money - present_money):
        problems.append(f"price {amount} from the fact sheet is missing from every document")

    # Percentages.
    allowed_pct = facts_percents(facts)
    for name, text in sorted(docs.items()):
        for pct in sorted(set(PERCENT_RE.findall(text))):
            if pct not in allowed_pct:
                problems.append(f"{name}: percentage {pct} is not in the fact sheet")
    for pct in sorted(allowed_pct - set(PERCENT_RE.findall(all_text))):
        problems.append(f"percentage {pct} from the fact sheet is missing from every document")

    # Times.
    fact_times = set(re.findall(r"\b\d{2}:\d{2}\b", fact_blob))
    for name, text in sorted(docs.items()):
        for t in sorted(doc_times(text) - fact_times):
            problems.append(f"{name}: time {t} (24-hour) is not in the fact sheet")
    for t in sorted(fact_times - doc_times(all_text)):
        problems.append(f"time {t} from the fact sheet is missing from every document")

    # Dates.
    fact_dates = set(re.findall(r"\b\d{4}-\d{2}-\d{2}\b", fact_blob))
    for name, text in sorted(docs.items()):
        for iso, written in sorted(doc_dates(text).items()):
            if iso not in fact_dates:
                problems.append(f"{name}: date {written} is not in the fact sheet")
    for iso in sorted(fact_dates - set(doc_dates(all_text))):
        problems.append(f"date {iso} from the fact sheet is missing from every document")

    # Phone numbers and emails.
    fact_phones = set(PHONE_RE.findall(fact_blob))
    fact_emails = set(EMAIL_RE.findall(fact_blob))
    for name, text in sorted(docs.items()):
        for phone in sorted(set(PHONE_RE.findall(text)) - fact_phones):
            problems.append(f"{name}: phone number {phone} is not in the fact sheet")
        for email in sorted(set(EMAIL_RE.findall(text)) - fact_emails):
            problems.append(f"{name}: email {email} is not in the fact sheet")

    # Any other number must at least appear somewhere in the fact sheet.
    fact_numbers = set(NUMBER_RE.findall(fact_blob))
    for name, text in sorted(docs.items()):
        for number in sorted(set(NUMBER_RE.findall(strip_handled(text))) - fact_numbers):
            problems.append(f"{name}: number {number} is not in the fact sheet")

    # Names and phrases that must be in a named document.
    for doc, phrase in required_phrases(facts):
        if phrase.lower() not in docs.get(doc, "").lower():
            problems.append(f"{doc}: expected text {phrase!r} is missing")

    return problems


def main() -> int:
    facts = json.loads((UNIVERSE / "facts.json").read_text("utf-8"))
    docs = {p.name: p.read_text("utf-8") for p in sorted((UNIVERSE / "docs").glob("*.md"))}
    problems = check(facts, docs)
    if problems:
        print(f"{len(problems)} problem(s) found:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print(f"OK: {len(docs)} documents are consistent with facts.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
