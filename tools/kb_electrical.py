"""The knowledge-base documents of the invented electrical business (D-098).

Rendered by `python -m tools.generate_kb_docs --universe universe-electrical`. The parts that do
not depend on the trade (about, hours, service area, the pricing layout) come from
tools/generate_kb_docs.py; what an electrician says about services, emergencies, policies and
common questions is here. Every figure comes from the fact sheet, and the consistency check runs
before anything is written.
"""

from typing import Any

from tools.generate_kb_docs import (
    about,
    bullets,
    call_out_text,
    document,
    hours,
    join_and,
    lower_first,
    money,
    pricing,
    sentence,
    service_area,
    t12,
)

SERVICE_DESCRIPTIONS = {
    "Emergency electrical repair": (
        "Fast help for sparks, smoke or a burning smell from an outlet, switch or panel, exposed "
        "live wires, and water reaching the wiring."
    ),
    "Panel upgrade": (
        "Replacing an old breaker panel or fuse box, or raising the service to 200 amps, "
        "including the permit."
    ),
    "Outlet and switch work": (
        "Replacing, adding or repairing outlets and switches, including GFCI outlets and dimmers."
    ),
    "Lighting and ceiling fan installation": (
        "Installing light fixtures and ceiling fans that you supply, and outdoor lighting."
    ),
    "EV charger installation": (
        "Installing a Level 2 charger for an electric car that you supply, including the permit."
    ),
    "Wiring repair and troubleshooting": (
        "Finding the cause of breakers that trip, outlets or lights that stopped working, and "
        "flickering, and repairing the wiring."
    ),
    "Electrical inspection": (
        "A whole-home electrical inspection with a written summary, for example before buying or "
        "selling a home."
    ),
    "General electrical repair": "Other electrical repairs that are not listed above.",
}

NOT_OFFERED_SENTENCES = {
    "Plumbing": "We do not do plumbing work.",
    "Gas line or gas appliance work": "We do not do gas line or gas appliance work.",
    "Heating and air conditioning": "We do not do heating or air conditioning work.",
    "Commercial or industrial buildings": "We do not work on commercial or industrial buildings.",
    "Solar panel installation": "We do not install solar panels.",
    "Utility power lines": "We do not work on power lines; they belong to the power utility.",
    "Security cameras and home networking": (
        "We do not install security cameras or home networks."
    ),
}

JOB_GROUPS = [
    ("outlet_and_switch", "Outlets and switches"),
    ("lighting_installation", "Lighting and ceiling fans"),
    ("ev_charger_installation", "EV chargers"),
    ("inspection", "Inspections"),
    ("other", "Smoke and carbon monoxide alarms"),
]


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


def electrical_pricing(f: dict[str, Any]) -> str:
    return pricing(f, JOB_GROUPS)


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
                "every day, including holidays. An electrician is usually dispatched within 2 "
                "hours. This is not guaranteed.",
            ),
            (
                "Emergency pricing",
                f"Emergency visits have an emergency call-out fee of {money(emerg_fee)} instead of "
                "the standard call-out fee. Labour and parts are charged as usual.",
            ),
            ("Urgent but not an emergency", sentence(e["urgent_not_emergency"])),
            ("If you see sparks or smoke, or smell burning", sentence(s["sparks_or_burning"])),
            ("If someone gets an electric shock", sentence(s["shock"])),
            ("If a power line is down", sentence(s["downed_line"])),
            ("If water reaches the wiring or the panel", sentence(s["water_and_electrics"])),
            (
                "If you smell gas",
                f"{sentence(s['gas_smell'])} {f['business']['name']} does not do gas work.",
            ),
            ("If a carbon monoxide alarm sounds", sentence(s["carbon_monoxide_alarm"])),
            ("Power cuts", sentence(f["policies"]["power_outages"])),
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
                f"{money(r['late_fee'])} applies. If no one is home or the electrician cannot get "
                f"in, {lower_first(sentence(r['no_show_or_no_access']))} "
                f"If an emergency visit is cancelled after an electrician has been dispatched, "
                f"{lower_first(sentence(r['emergency_cancelled_after_dispatch']))}",
            ),
            (
                "Warranty",
                f"Our workmanship is covered for {w['workmanship_months']} months. "
                f"Parts are covered by the manufacturer's warranty, not by "
                f"{f['business']['name']}. "
                "The warranty does not apply to work that someone else has altered or repaired.",
            ),
            ("Written estimates", sentence(p["estimates"])),
            ("Permits", sentence(p["permits"])),
            ("Refunds and disputes", sentence(p["refunds_and_disputes"])),
            ("Insurance claims", sentence(p["insurance"])),
            ("Power cuts", sentence(p["power_outages"])),
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
            "How much does it cost to replace an outlet or a switch?",
            f"Replacing an outlet or a switch is {price('Outlet or switch replacement')} each. A "
            f"GFCI outlet is {price('GFCI outlet')} each and a dimmer switch is "
            f"{price('Dimmer switch')} each.",
        ),
        (
            "How much does an EV charger installation cost?",
            f"A Level 2 charger up to 25 feet from the panel is "
            f"{price('Level 2 EV charger')}, including the permit, when you supply the charger. "
            "Longer runs, and a panel upgrade if the panel has no room, are priced by quote.",
        ),
        (
            "Do you upgrade electrical panels?",
            "Yes. Panel upgrades, including from 100 to 200 amps, are priced by quote after a "
            "site visit. The price includes the permit.",
        ),
        (
            "My breaker keeps tripping. What should I do?",
            "A breaker that keeps tripping is urgent but not an emergency. We find the cause "
            "and repair the wiring, priced as hourly labour plus parts. If you see sparks or "
            f"smoke, or smell burning, {lower_first(sentence(s['sparks_or_burning']))}",
        ),
        (
            "Do you do plumbing or gas work?",
            f"No. If you smell gas, {lower_first(sentence(s['gas_smell']))}",
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
            "urgent but not an emergency, such as no power to part of the home, we book the next "
            "available visit, and the same day if you ask before noon and there is room. "
            f"{sentence(f['policies']['communication'])}",
        ),
        (
            "The whole street has no power. Can you help?",
            sentence(f["policies"]["power_outages"]),
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
        ("Do I need a permit?", sentence(f["policies"]["permits"])),
        ("Will you help with my insurance claim?", sentence(f["policies"]["insurance"])),
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
    "pricing.md": electrical_pricing,
    "service-area.md": service_area,
    "services.md": services,
}
