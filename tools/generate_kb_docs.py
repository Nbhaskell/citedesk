"""Render the knowledge-base documents from universe/facts.json.

Run: python -m tools.generate_kb_docs

Fix the generator, not the generated files. The output is deterministic (no randomness, so no
seed). After writing, the consistency check runs and the command fails if any document disagrees
with the fact sheet. Every figure in the text comes from facts.json.
"""

import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

from tools.check_consistency import check

GENERATOR_VERSION = 1
REPO_ROOT = Path(__file__).resolve().parent.parent
UNIVERSE = REPO_ROOT / "universe"

SERVICE_DESCRIPTIONS = {
    "Emergency plumbing repair": (
        "Fast help for burst pipes, leaks that cannot be stopped, sewage backing up and flooding."
    ),
    "Drain cleaning": "Clearing blocked or slow sinks, tubs, showers and toilets.",
    "Main sewer line cleaning": "Clearing the main line that carries waste out of the house.",
    "Sewer line repair": (
        "Repairing a damaged main sewer line once a camera inspection has shown the problem."
    ),
    "Leak detection": "Electronic detection to find the source of a hidden leak.",
    "Plumbing leak repair": "Repairing leaking pipes and fittings.",
    "Slab leak repair": (
        "Repairing a leak in pipes under a concrete slab floor, after leak detection has found it."
    ),
    "Water heater service and replacement": (
        "Flushing tank water heaters and replacing tank units. Tankless installation is by quote."
    ),
    "Fixture installation": (
        "Installing faucets, toilets and garbage disposals that you supply, "
        "and replacing fixture shut-off valves."
    ),
    "Plumbing inspection": (
        "A whole-home inspection with a written summary, "
        "or a camera inspection of a drain or sewer line."
    ),
    "General plumbing repair": "Other plumbing repairs that are not listed above.",
}

NOT_OFFERED_SENTENCES = {
    "Gas line or gas appliance work": "We do not do gas line or gas appliance work.",
    "Electrical work": "We do not do electrical work.",
    "Heating and air conditioning": "We do not do heating or air conditioning work.",
    "Commercial or industrial buildings": "We do not work on commercial or industrial buildings.",
    "Septic tank pumping": "We do not pump out septic tanks.",
    "Well pumps": "We do not work on well pumps.",
    "Irrigation and sprinkler systems": "We do not work on irrigation or sprinkler systems.",
    "Mould remediation": "We do not do mould remediation.",
    "Roof leaks": "We do not repair roof leaks.",
}

JOB_GROUPS = [
    ("drain_cleaning", "Drain cleaning"),
    ("leak_repair", "Leak detection"),
    ("inspection", "Inspections"),
    ("water_heater", "Water heaters"),
    ("fixture_installation", "Fixtures"),
]


# --- small helpers ---------------------------------------------------------------------------


def money(amount: float) -> str:
    return f"${int(amount):,}"


def t12(hhmm: str) -> str:
    hour, minute = (int(p) for p in hhmm.split(":"))
    if (hour, minute) == (12, 0):
        return "noon"
    return f"{hour % 12 or 12}:{minute:02d} {'am' if hour < 12 else 'pm'}"


def fx(text: str) -> str:
    """Fact-sheet text with any 24-hour times written the way a person would."""
    return re.sub(r"\b\d{2}:\d{2}\b", lambda m: t12(m.group(0)), text)


def long_date(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d:%B} {d.day}, {d.year}"


def sentence(text: str) -> str:
    text = fx(text.strip())
    return text if text.endswith((".", "!", "?")) else text + "."


def plain(text: str) -> str:
    """Drop a trailing parenthetical such as '(invented street and town)'."""
    return text.split(" (")[0]


def lower_first(text: str) -> str:
    return text[:1].lower() + text[1:]


def join_and(items: list[str]) -> str:
    if len(items) <= 2:
        return " and ".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def bullets(items: list[str]) -> str:
    return "\n".join(f"- {i}" for i in items)


def call_out_text(f: dict[str, Any]) -> str:
    return (
        f"The standard call-out fee is {money(f['pricing']['call_out_fee']['price'])}. It covers "
        "travel and diagnosis, and it is credited toward the work if the customer approves the "
        "work during the same visit."
    )


def document(title: str, sections: list[tuple[str, str]]) -> str:
    parts = [f"# {title}"]
    for heading, body in sections:
        parts.append(f"## {heading}\n\n{body.strip()}")
    return "\n\n".join(parts) + "\n"


# --- the documents ---------------------------------------------------------------------------


def about(f: dict[str, Any]) -> str:
    b = f["business"]
    contact = [
        f"Office phone: {b['phone']}",
        f"Emergency line: {b['emergency_phone']}, answered 24 hours a day, every day, "
        "including holidays",
        f"Email: {b['email']}",
        f"Address: {plain(b['address'])}",
    ]
    staff = [f"{s['name']}, {s['role']}: {s['handles']}" for s in f["staff"]]
    return document(
        f"About {b['name']}",
        [
            (
                "Who we are",
                f"{b['name']} is a {b['type']} in Alderbrook. {sentence(plain(b['credentials']))} "
                f"We serve {lower_first(sentence(b['customers']))}",
            ),
            (
                "How to contact us",
                bullets(contact) + "\n\nCustomers write to us through the web form or by email.",
            ),
            ("Who handles what", bullets(staff)),
        ],
    )


def hours(f: dict[str, Any]) -> str:
    h = f["hours"]
    mf, sat = h["office"]["monday_to_friday"], h["office"]["saturday"]
    sv = h["scheduled_visits"]
    sv_mf, sv_sat = sv["monday_to_friday"], sv["saturday"]
    closed = [f"{d['name']}: {long_date(d['date'])}" for d in h["closed_dates"]]
    return document(
        "Hours and scheduling",
        [
            (
                "Office hours",
                f"The office is open Monday to Friday from {t12(mf['open'])} to {t12(mf['close'])} "
                f"and on Saturday from {t12(sat['open'])} to {t12(sat['close'])}. "
                "The office is closed on Sunday.",
            ),
            (
                "Scheduled visits",
                f"Scheduled visits run Monday to Friday, with the first arrival at "
                f"{t12(sv_mf['first_arrival'])} and the last arrival at "
                f"{t12(sv_mf['last_arrival'])}. "
                f"On Saturday the first arrival is at {t12(sv_sat['first_arrival'])} and the last "
                f"arrival is at {t12(sv_sat['last_arrival'])}. "
                f"Each arrival window is {sv['arrival_windows_hours']} hours. "
                f"We call {sv['courtesy_call_minutes_before']} minutes before we arrive.",
            ),
            (
                "Emergency line",
                f"The emergency line, {f['business']['emergency_phone']}, is answered 24 hours a "
                "day, every day, including holidays.",
            ),
            ("Holidays and closures", bullets(closed) + "\n\n" + sentence(h["closed_dates_note"])),
            ("How soon we can come", sentence(f["emergencies"]["standard_lead_time"])),
        ],
    )


def service_area(f: dict[str, Any]) -> str:
    a = f["service_area"]
    return document(
        "Service area",
        [
            ("Neighbourhoods we serve", f"We serve {join_and(a['core'])}."),
            (
                "Outer areas",
                f"We also serve {join_and(a['outer']['areas'])}. "
                f"A travel fee of {money(a['outer']['travel_fee'])} applies to these areas.",
            ),
            ("Areas we do not serve", f"We do not serve {lower_first(a['not_served'])}."),
            (
                "Types of property",
                f"We serve {lower_first(sentence(f['business']['customers']))} "
                "We do not work on commercial or industrial buildings.",
            ),
            (
                "What we need to book a visit",
                "Please tell us:\n\n" + bullets(f["contact_rules"]["booking_requires"]),
            ),
        ],
    )


def services(f: dict[str, Any]) -> str:
    sections = [
        (s["name"], f"{SERVICE_DESCRIPTIONS[s['name']]} Pricing: {s['pricing']}.")
        for s in f["services_offered"]
    ]
    sections.append(
        (
            "How to book",
            "To book a visit, please tell us:\n\n"
            + bullets(f["contact_rules"]["booking_requires"])
            + "\n\n"
            + sentence(f["policies"]["communication"]),
        )
    )
    intro = f"{f['business']['name']} offers the services below."
    return document("Services", [("What we offer", intro), *sections])


def pricing(f: dict[str, Any]) -> str:
    p = f["pricing"]
    emerg, labour = p["emergency_call_out_fee"], p["labour"]
    pay = p["payment"]
    sections: list[tuple[str, str]] = [
        ("Call-out fee", call_out_text(f)),
        (
            "Emergency call-out fee",
            f"The emergency call-out fee is {money(emerg['price'])}. It is charged for "
            "emergency visits, and for any visit outside scheduled-visit hours, on Sundays or "
            "on closed dates. It replaces the standard call-out fee.",
        ),
        (
            "Labour",
            f"Labour is {money(labour['price_per_hour'])} per hour, billed in 30-minute "
            "increments after the first hour, with a minimum of 1 hour. Labour does not include "
            "parts.",
        ),
        (
            "Parts and sales tax",
            "Parts are priced on the written estimate. Parts carry sales tax and labour does not. "
            f"Sales tax on parts is {round(p['parts']['parts_sales_tax_rate'] * 100, 6):g}%.",
        ),
        (
            "Travel fee for outer areas",
            f"A travel fee of {money(f['service_area']['outer']['travel_fee'])} applies in "
            f"{join_and(f['service_area']['outer']['areas'])}.",
        ),
    ]
    for service_type, heading in JOB_GROUPS:
        lines = []
        for job in p["flat_price_jobs"]:
            if job["service_type"] != service_type:
                continue
            line = f"{job['job']}: {money(job['price'])}"
            if job.get("price_note") == "starting price":
                line += " (starting price)"
            if job.get("note"):
                line += f". {sentence(job['note'])}"
            lines.append(line)
        if lines:
            sections.append((heading, bullets(lines)))
    sections += [
        ("Jobs priced by quote", bullets(p["quote_only"])),
        (
            "Written estimates",
            f"No work over {money(p['written_estimate_required_over'])} starts without a written "
            "estimate that the customer has approved.",
        ),
        (
            "Discounts",
            "We do not offer discounts. That includes senior, military, repeat-customer and "
            "price-match discounts.",
        ),
        (
            "Payment and invoices",
            f"We accept {join_and(pay['methods'])}. Payment is due {lower_first(pay['when'])}. "
            f"The invoice is {lower_first(sentence(pay['invoice']))} "
            f"A late fee of {round(pay['late_fee_percent_per_month'], 6):g}% per month applies to "
            f"invoices unpaid after {pay['late_fee_after_days']} days.",
        ),
    ]
    return document("Pricing", sections)


def emergencies(f: dict[str, Any]) -> str:
    e, s = f["emergencies"], f["safety_instructions"]
    emerg_fee = f["pricing"]["emergency_call_out_fee"]["price"]
    return document(
        "Emergencies and safety",
        [
            ("What counts as an emergency", sentence(e["definition"])),
            (
                "How to reach us in an emergency",
                f"Call {f['business']['emergency_phone']}. The line is answered 24 hours a day, "
                "every day, including holidays. A technician is usually dispatched within 2 hours. "
                "This is not guaranteed.",
            ),
            (
                "Emergency pricing",
                f"Emergency visits have an emergency call-out fee of {money(emerg_fee)} instead of "
                "the standard call-out fee. Labour and parts are charged as usual.",
            ),
            ("Urgent but not an emergency", sentence(e["urgent_not_emergency"])),
            ("If water will not stop", sentence(s["water_wont_stop"])),
            (
                "If you smell gas",
                f"{sentence(s['gas_smell'])} {f['business']['name']} does not do gas work.",
            ),
            ("If sewage is backing up", sentence(s["sewage_backup"])),
            ("If a carbon monoxide alarm sounds", sentence(s["carbon_monoxide_alarm"])),
            ("Water damage", sentence(f["policies"]["water_damage"])),
        ],
    )


def policies(f: dict[str, Any]) -> str:
    p = f["policies"]
    r, w = p["reschedule_and_cancel"], p["warranty"]
    return document(
        "Policies",
        [
            (
                "Rescheduling and cancelling",
                f"You can reschedule or cancel free of charge with at least "
                f"{r['free_with_notice_hours']} hours' notice. With less notice, a fee of "
                f"{money(r['late_fee'])} applies. If no one is home or the technician cannot get "
                f"in, {lower_first(sentence(r['no_show_or_no_access']))} "
                f"If an emergency visit is cancelled after a technician has been dispatched, "
                f"{lower_first(sentence(r['emergency_cancelled_after_dispatch']))}",
            ),
            (
                "Warranty",
                f"Our workmanship is covered for {w['workmanship_months']} months. "
                f"Parts are covered by the manufacturer's warranty, not by "
                f"{f['business']['name']}. {sentence(w['drain_cleaning'])} "
                "The warranty does not apply to work that someone else has altered or repaired.",
            ),
            ("Written estimates", sentence(p["estimates"])),
            ("Refunds and disputes", sentence(p["refunds_and_disputes"])),
            ("Insurance claims", sentence(p["insurance"])),
            ("Water damage", sentence(p["water_damage"])),
            ("Access to your home", sentence(p["access"])),
            ("Confirmation of visits", sentence(p["communication"])),
            (
                "Work we do not do",
                "We do not do work in these areas: "
                f"{join_and([lower_first(i) for i in p['not_offered']])}.",
            ),
            *[(item, NOT_OFFERED_SENTENCES[item]) for item in p["not_offered"]],
        ],
    )


def faq(f: dict[str, Any]) -> str:
    p, s = f["pricing"], f["safety_instructions"]
    h, area = f["hours"], f["service_area"]
    jobs = {j["job"]: j for j in p["flat_price_jobs"]}

    def price(prefix: str) -> str:
        matches = [j for name, j in jobs.items() if name.startswith(prefix)]
        if len(matches) != 1:
            raise ValueError(f"expected exactly one flat-price job starting with {prefix!r}")
        return money(matches[0]["price"])

    sat = h["scheduled_visits"]["saturday"]
    r = f["policies"]["reschedule_and_cancel"]
    qa = [
        (
            "Do you charge to come out?",
            f"Yes. {call_out_text(f)} Emergency visits and visits outside scheduled-visit hours "
            f"have an emergency call-out fee of {money(p['emergency_call_out_fee']['price'])} "
            "instead.",
        ),
        (
            "How much does drain cleaning cost?",
            f"Drain cleaning for one fixture starts at {price('Drain cleaning')}. "
            f"Main sewer line cleaning is {price('Main sewer line cleaning')}.",
        ),
        (
            "How much does a new water heater cost?",
            f"A 40-gallon tank water heater is {price('Water heater replacement, 40')} installed "
            f"and a 50-gallon tank is {price('Water heater replacement, 50')} installed. Both "
            "prices include the permit and removal of the old unit. Tankless water heater "
            "installation is priced by quote.",
        ),
        (
            "Can you find a hidden leak?",
            f"Yes. Electronic leak detection is {price('Leak detection')}, and it is credited "
            "toward the repair if the customer approves the repair during the same visit. Leak "
            "and pipe repairs are priced by quote, as hourly labour plus parts.",
        ),
        (
            "Do you repair sewer lines?",
            f"Yes. Sewer line repair is priced by quote after a camera inspection. A camera "
            f"inspection of a drain or sewer line is {price('Camera inspection')}.",
        ),
        (
            "Do you fix slab leaks?",
            f"Yes. Slab leak repair is priced by quote after leak detection, which is "
            f"{price('Leak detection')}.",
        ),
        (
            "Do you work on gas lines or gas appliances?",
            f"No, we do not do gas work. If you smell gas, {lower_first(sentence(s['gas_smell']))}",
        ),
        (
            "Do you work on weekends?",
            f"Scheduled visits run on Saturday, with the first arrival at "
            f"{t12(sat['first_arrival'])} and the last arrival at {t12(sat['last_arrival'])}. "
            "The office is closed on Sunday. The emergency line is answered 24 hours a day, "
            "every day.",
        ),
        (
            "Can someone come today?",
            f"For an emergency, call {f['business']['emergency_phone']}. For a problem that is "
            "urgent but not an emergency, such as no hot water, we book the next available "
            "visit, and the same day if you ask before noon and there is room. "
            f"{sentence(f['policies']['communication'])}",
        ),
        (
            "Do you offer discounts?",
            "No. We do not offer discounts, including senior, military, repeat-customer and "
            "price-match discounts.",
        ),
        ("Do I need to be home?", sentence(f["policies"]["access"])),
        (
            "Do you work on commercial buildings?",
            f"No. We serve {lower_first(sentence(f['business']['customers']))}",
        ),
        ("Will you help with my insurance claim?", sentence(f["policies"]["insurance"])),
        ("Do you clean up water damage?", sentence(f["policies"]["water_damage"])),
        (
            "Do you serve my area?",
            f"We serve {join_and(area['core'])}. We also serve {join_and(area['outer']['areas'])}, "
            f"where a travel fee of {money(area['outer']['travel_fee'])} applies. "
            f"We do not serve {lower_first(area['not_served'])}.",
        ),
        (
            "What if I need to reschedule or cancel?",
            f"You can reschedule or cancel free of charge with at least "
            f"{r['free_with_notice_hours']} hours' notice. With less notice, a fee of "
            f"{money(r['late_fee'])} applies.",
        ),
    ]
    return document("Frequently asked questions", [(q, a) for q, a in qa])


RENDERERS = {
    "about.md": about,
    "emergencies.md": emergencies,
    "faq.md": faq,
    "hours.md": hours,
    "policies.md": policies,
    "pricing.md": pricing,
    "service-area.md": service_area,
    "services.md": services,
}


def render_docs(facts: dict[str, Any]) -> dict[str, str]:
    return {name: render(facts) for name, render in RENDERERS.items()}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    facts_path = UNIVERSE / "facts.json"
    facts = json.loads(facts_path.read_text("utf-8"))
    docs = render_docs(facts)

    problems = check(facts, docs)
    if problems:
        print(f"Not writing: {len(problems)} consistency problem(s):")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    out_dir = UNIVERSE / "docs"
    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in out_dir.glob("*.md"):
        if stale.name not in docs:
            stale.unlink()
    for name, text in docs.items():
        (out_dir / name).write_bytes(text.encode("utf-8"))

    manifest = {
        "synthetic": True,
        "note": "SYNTHETIC TEST DATA. Generated by tools/generate_kb_docs.py.",
        "generator": {"name": "generate_kb_docs", "version": GENERATOR_VERSION},
        "seed": None,
        "seed_note": "Documents are deterministic. Same fact sheet, same files.",
        "facts_sha256": sha256_bytes(facts_path.read_bytes()),
        "docs": {name: sha256_bytes((out_dir / name).read_bytes()) for name in sorted(docs)},
    }
    (UNIVERSE / "manifest.json").write_bytes(
        (json.dumps(manifest, indent=2) + "\n").encode("utf-8")
    )
    print(f"Wrote {len(docs)} documents to {out_dir.relative_to(REPO_ROOT)}; consistency OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
