"""FastAPI app. Phase 0 exposes GET /api/status only."""

from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel

from citedesk import __version__
from citedesk.config import Settings


class ComponentStatus(BaseModel):
    status: Literal["not_checked"]


class Components(BaseModel):
    database: ComponentStatus
    model: ComponentStatus
    knowledge_base: ComponentStatus


class StatusResponse(BaseModel):
    status: Literal["ok"]
    app: Literal["citedesk"]
    version: str
    synthetic_data: bool
    model: str
    components: Components


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(title="Citedesk", version=__version__)

    @app.get("/api/status", response_model=StatusResponse)
    def status() -> StatusResponse:
        # Component health is not checked yet: the database arrives in Phase 2, the
        # model in Phase 4 and the knowledge base in Phase 5.
        not_checked = ComponentStatus(status="not_checked")
        return StatusResponse(
            status="ok",
            app="citedesk",
            version=__version__,
            synthetic_data=settings.synthetic_data,
            model=settings.llm_model,
            components=Components(
                database=not_checked, model=not_checked, knowledge_base=not_checked
            ),
        )

    return app
