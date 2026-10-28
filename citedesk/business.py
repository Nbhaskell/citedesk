"""The business's own details, read from the fact sheet (universe/facts.json).

Only what a reply needs: the name for the sign-off, and the contact details a draft may repeat
without the figure check treating them as invented.
"""

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Business:
    name: str
    phone: str
    emergency_phone: str
    email: str

    @property
    def trusted_text(self) -> str:
        return f"{self.name} {self.phone} {self.emergency_phone} {self.email}"


def load_business(path: Path) -> Business:
    data = json.loads(path.read_text("utf-8"))
    details = data.get("business", {})
    missing = [key for key in ("name", "phone", "emergency_phone", "email") if not details.get(key)]
    if missing:
        raise ValueError(f"the fact sheet's business section lacks: {', '.join(missing)}")
    return Business(
        name=str(details["name"]),
        phone=str(details["phone"]),
        emergency_phone=str(details["emergency_phone"]),
        email=str(details["email"]),
    )
