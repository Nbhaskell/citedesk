"""Run the API: python -m citedesk"""

import uvicorn

from citedesk.api import create_app
from citedesk.business import load_business
from citedesk.config import Settings
from citedesk.knowledge import RagProjectKB
from citedesk.providers.ollama import OllamaProvider

# Fixed on purpose: v1 has no authentication, so it must never listen on a network interface.
HOST = "127.0.0.1"


def main() -> None:
    settings = Settings()
    # The only place the real model and knowledge base are attached: tests and library code build
    # the app without them.
    app = create_app(
        settings,
        llm=OllamaProvider.from_settings(settings),
        kb=RagProjectKB(settings.rag_url),
        business=load_business(settings.business_facts_path),
    )
    uvicorn.run(app, host=HOST, port=settings.port)


if __name__ == "__main__":
    main()
