"""Write the API's OpenAPI description to web/openapi.json, the input of the type generator.

Run:
    python -m tools.export_openapi           write web/openapi.json
    python -m tools.export_openapi --check   exit 1 if the file is out of date

The web app's TypeScript types (web/src/api/schema.d.ts) are generated from this file with
`npm run gen:api` in web/. The file is built from the app's code alone (no settings, no database,
no model), sorted and indented so it only changes when the API does.
"""

import argparse
import json
import sys
from pathlib import Path

from citedesk.api import create_app
from citedesk.config import Settings

REPO_ROOT = Path(__file__).resolve().parent.parent
OPENAPI_FILE = REPO_ROOT / "web/openapi.json"


def render() -> str:
    app = create_app(Settings(_env_file=None), start_worker=False)
    return json.dumps(app.openapi(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--check", action="store_true", help="fail if the file is out of date")
    args = parser.parse_args(argv)
    text = render()
    if args.check:
        current = OPENAPI_FILE.read_text(encoding="utf-8") if OPENAPI_FILE.exists() else ""
        if current != text:
            print("web/openapi.json is out of date; run: python -m tools.export_openapi")
            return 1
        print("web/openapi.json is current")
        return 0
    OPENAPI_FILE.parent.mkdir(parents=True, exist_ok=True)
    OPENAPI_FILE.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {OPENAPI_FILE.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
