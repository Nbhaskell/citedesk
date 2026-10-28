"""Run the API: python -m citedesk"""

import uvicorn

from citedesk.api import create_app
from citedesk.config import Settings
from citedesk.providers.ollama import OllamaProvider

# Fixed on purpose: v1 has no authentication, so it must never listen on a network interface.
HOST = "127.0.0.1"


def main() -> None:
    settings = Settings()
    # The only place a real model is attached: tests and library code build the app without one.
    uvicorn.run(
        create_app(settings, llm=OllamaProvider.from_settings(settings)),
        host=HOST,
        port=settings.port,
    )


if __name__ == "__main__":
    main()
