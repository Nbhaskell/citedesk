"""The HTTP API (docs/TRD.md section 6), as far as Phase 6 goes (no endpoint sends anything).

    GET  /api/status                 health, queue depth, whether the worker runs
    POST /api/inquiries              store one inquiry (answers at once; the pipeline runs later)
    POST /api/inquiries/import       a JSONL or CSV file as the request body
    GET  /api/inquiries              list, filtered and paged in review-queue order
    GET  /api/inquiries/{id}         everything known about one inquiry
    POST /api/drafts/{id}/approve    approve a draft, optionally with the reviewer's edit
    POST /api/drafts/{id}/reject     reject a draft (a reason is required)
    POST /api/drafts/{id}/redraft    write the next version of a rejected draft from guidance
    POST /api/inquiries/{id}/reprocess  put a failed inquiry back to where its stage started
    POST /api/inquiries/{id}/escalate   send an item waiting for review to the owner (note required)
    POST /api/inquiries/{id}/resolve    close an escalated or rejected item
    GET  /api/drafts/{id}/export     the approved text; changes nothing
    POST /api/drafts/{id}/export     record that the approved text was copied
    GET  /api/insights               counts and review times

Every response carries an `X-Request-ID`. Every error has the one shape
`{"error": {"code", "message", "request_id"}}`, and a message never repeats what the caller sent.
A database connection is opened inside each request, so no connection crosses threads.
"""

import base64
import binascii
import json
import logging
import sqlite3
import uuid
from collections.abc import AsyncIterator, Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager, contextmanager
from typing import Annotated, Any, Literal

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException

from citedesk import __version__, events, health, insights, intake, pipeline, repo, review
from citedesk.business import Business, load_business
from citedesk.config import Settings
from citedesk.db import connect, migrate, utc_now
from citedesk.insights import Insights
from citedesk.intake import (
    DuplicateExternalId,
    ImportFormatError,
    IntakeFailure,
    InvalidInquiry,
    NewInquiry,
)
from citedesk.knowledge import KnowledgeBase
from citedesk.models import (
    AuditEvent,
    Channel,
    Classification,
    Draft,
    DraftCheck,
    Escalation,
    Extraction,
    Inquiry,
    InquiryStatus,
    Intent,
    ReasonCode,
    Retrieval,
    Route,
    Screening,
    Urgency,
)
from citedesk.pipeline import PipelineWorker
from citedesk.providers import LLMProvider, LLMStepFailed

logger = logging.getLogger("citedesk.api")

MAX_IMPORT_BYTES = 5 * 1024 * 1024
JSONL_TYPES = {"application/x-ndjson", "application/jsonl", "application/json-lines", "text/jsonl"}
IMPORT_REASONS = {
    "no_header": "the file has no header row",
    "unknown_columns": "the file has columns that are not allowed",
    "missing_body_column": "the file has no body column",
    "too_many_records": "the file has too many records",
}


# --- response models -------------------------------------------------------------------------


class ComponentStatus(BaseModel):
    status: Literal["ok", "error", "not_checked"]
    reason: str | None = None


class Components(BaseModel):
    database: ComponentStatus
    model: ComponentStatus
    knowledge_base: ComponentStatus


class Attention(BaseModel):
    needs_review: int
    escalated: int
    failed: int
    urgent_open: int


class StatusResponse(BaseModel):
    status: Literal["ok", "degraded"]
    app: Literal["citedesk"]
    version: str
    synthetic_data: bool
    model: str
    components: Components
    queue_depth: int
    worker_running: bool
    attention: Attention
    checked_at: str | None


class SubmitResponse(BaseModel):
    id: int
    status: InquiryStatus
    duplicate_of: int | None
    sensitive_data_masked: bool


class InquirySummary(BaseModel):
    id: int
    external_id: str | None
    channel: Channel
    received_at: str
    sender_name: str | None
    subject: str | None
    summary: str | None
    status: InquiryStatus
    route: Route | None
    urgency: Urgency | None
    primary_intent: Intent | None
    duplicate_of: int | None
    is_synthetic: bool


class InquiryList(BaseModel):
    items: list[InquirySummary]
    next_cursor: str | None


class InquiryDetail(BaseModel):
    inquiry: Inquiry
    screening: Screening | None
    classification: Classification | None
    extraction: Extraction | None
    escalations: list[Escalation]
    retrievals: list[Retrieval]
    draft: Draft | None
    checks: list[DraftCheck]
    history: list[AuditEvent]
    duplicates: list[int]


class ApproveBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    edited_body: str | None = None
    review_seconds: int | None = None


class RejectBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str
    review_seconds: int | None = None


class BusinessOut(BaseModel):
    name: str
    phone: str
    emergency_phone: str
    email: str


class RuleOut(BaseModel):
    code: ReasonCode
    enabled: bool
    set_by: Literal["code", "environment"]


class SettingsView(BaseModel):
    business: BusinessOut | None
    draft_max_words: int
    model: str
    synthetic_data: bool
    rules: list[RuleOut]


class RedraftBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    guidance: str


class EscalateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    note: str


class ResolveBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    note: str | None = None


class ExportText(BaseModel):
    inquiry_id: int
    draft_id: int
    subject: str | None
    body: str


class RejectionOut(BaseModel):
    line: int
    code: str


class ImportResponse(BaseModel):
    created: int
    already_imported: int
    linked_duplicates: int
    rejected: list[RejectionOut]
    ids: list[int]


# --- errors ----------------------------------------------------------------------------------


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def request_id_of(request: Request) -> str:
    return str(getattr(request.state, "request_id", None) or uuid.uuid4().hex)


def error_response(request: Request, status: int, code: str, message: str) -> JSONResponse:
    rid = request_id_of(request)
    return JSONResponse(
        {"error": {"code": code, "message": message, "request_id": rid}},
        status_code=status,
        headers={"X-Request-ID": rid},
    )


def field_names(error: RequestValidationError) -> list[str]:
    names: set[str] = set()
    for item in error.errors():
        parts = [
            str(p)
            for p in item["loc"]
            if p not in ("body", "query", "path") or len(item["loc"]) == 1
        ]
        if len(item["loc"]) > 1:
            parts = [str(p) for p in item["loc"][1:]]
        if parts and not parts[0].isdigit():
            names.add(".".join(parts))
    return sorted(names)


# --- cursors ---------------------------------------------------------------------------------


def encode_cursor(inquiry: Inquiry) -> str:
    key = [
        repo.urgency_rank(inquiry.urgency.value if inquiry.urgency else None),
        inquiry.received_at,
        inquiry.id,
    ]
    return base64.urlsafe_b64encode(json.dumps(key).encode()).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[int, str, int]:
    try:
        key = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
    except (binascii.Error, ValueError):
        raise ApiError(422, "invalid_cursor", "The cursor is not valid.") from None
    if not (
        isinstance(key, list)
        and len(key) == 3
        and isinstance(key[0], int)
        and isinstance(key[1], str)
        and isinstance(key[2], int)
    ):
        raise ApiError(422, "invalid_cursor", "The cursor is not valid.")
    return key[0], key[1], key[2]


# --- the app ---------------------------------------------------------------------------------


def create_app(
    settings: Settings | None = None,
    *,
    start_worker: bool = True,
    worker_poll_seconds: float = 2.0,
    llm: LLMProvider | None = None,
    kb: KnowledgeBase | None = None,
    business: Business | None = None,
    get_json: health.GetFn | None = None,
) -> FastAPI:
    """Build the API. The worker reads inquiries with `llm`; without one it only screens them.
    With `kb` and `business` as well it goes on to retrieve, draft and check a reply."""
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        settings.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = connect(settings.db_path)
        try:
            migrate(conn)
        finally:
            conn.close()
        worker = (
            PipelineWorker(
                settings, poll_seconds=worker_poll_seconds, llm=llm, kb=kb, business=business
            )
            if start_worker
            else None
        )
        app.state.worker = worker
        if worker is not None:
            worker.start()
        try:
            yield
        finally:
            if worker is not None:
                worker.stop()
            app.state.worker = None

    app = FastAPI(title="Citedesk", version=__version__, lifespan=lifespan)
    app.state.worker = None
    app.state.checks = None  # (model, knowledge base, time) after the first POST /api/status/check

    @contextmanager
    def db() -> Iterator[sqlite3.Connection]:
        conn = connect(settings.db_path)
        try:
            yield conn
        finally:
            conn.close()

    def wake_worker() -> None:
        worker: PipelineWorker | None = app.state.worker
        if worker is not None:
            worker.notify()

    @app.middleware("http")
    async def add_request_id(request: Request, call_next: Any) -> Response:
        request.state.request_id = uuid.uuid4().hex
        response: Response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, error: ApiError) -> JSONResponse:
        return error_response(request, error.status, error.code, error.message)

    @app.exception_handler(RequestValidationError)
    async def handle_validation(request: Request, error: RequestValidationError) -> JSONResponse:
        if any(item["type"] == "json_invalid" for item in error.errors()):
            message = "The request body is not valid JSON."
        else:
            names = field_names(error)
            message = (
                f"Invalid or missing field(s): {', '.join(names)}."
                if names
                else "The request is not valid."
            )
        return error_response(request, 422, "validation_error", message)

    @app.exception_handler(StarletteHTTPException)
    async def handle_http(request: Request, error: StarletteHTTPException) -> JSONResponse:
        codes = {
            404: "not_found",
            405: "method_not_allowed",
            413: "payload_too_large",
            415: "unsupported_media_type",
        }
        phrases = {404: "Not found.", 405: "That method is not allowed here."}
        return error_response(
            request,
            error.status_code,
            codes.get(error.status_code, f"http_{error.status_code}"),
            phrases.get(error.status_code, "The request could not be handled."),
        )

    @app.exception_handler(review.NotFound)
    async def handle_review_not_found(request: Request, error: review.NotFound) -> JSONResponse:
        return error_response(request, 404, "not_found", str(error))

    @app.exception_handler(review.WrongState)
    async def handle_wrong_state(request: Request, error: review.WrongState) -> JSONResponse:
        return error_response(request, 409, "wrong_state", str(error))

    @app.exception_handler(review.InvalidReview)
    async def handle_invalid_review(request: Request, error: review.InvalidReview) -> JSONResponse:
        return error_response(request, 422, "invalid_review", str(error))

    @app.exception_handler(LLMStepFailed)
    async def handle_model_failed(request: Request, error: LLMStepFailed) -> JSONResponse:
        logger.warning("model step failed: %s", error.reason)
        return error_response(
            request,
            502,
            "model_failed",
            "The model gave no usable reply. Nothing was changed; try again.",
        )

    @app.exception_handler(DuplicateExternalId)
    async def handle_duplicate(request: Request, error: DuplicateExternalId) -> JSONResponse:
        message = (
            "An inquiry with this channel and external id already exists "
            f"(inquiry {error.existing_id})."
        )
        return error_response(request, 409, "duplicate_external_id", message)

    @app.exception_handler(InvalidInquiry)
    async def handle_invalid(request: Request, error: InvalidInquiry) -> JSONResponse:
        return error_response(request, 422, "invalid_inquiry", str(error))

    @app.exception_handler(IntakeFailure)
    async def handle_intake_failure(request: Request, error: IntakeFailure) -> JSONResponse:
        logger.error("intake failed: %s", type(error.__cause__).__name__)
        return error_response(
            request,
            500,
            "screening_failed",
            "The message could not be checked, so it was not stored.",
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, error: Exception) -> JSONResponse:
        logger.error("unhandled error: %s", type(error).__name__)
        return error_response(request, 500, "internal_error", "Something went wrong on the server.")

    # --- routes ---

    def build_status() -> StatusResponse:
        database = "ok"
        depth = 0
        counts = {"needs_review": 0, "escalated": 0, "failed": 0, "urgent_open": 0}
        try:
            with db() as conn:
                row = conn.execute(
                    "SELECT "
                    "COALESCE(SUM(status = 'received'), 0) AS queued, "
                    "COALESCE(SUM(status = 'needs_review'), 0) AS needs_review, "
                    "COALESCE(SUM(status = 'escalated'), 0) AS escalated, "
                    "COALESCE(SUM(status = 'failed'), 0) AS failed, "
                    "COALESCE(SUM(urgency = 'urgent' AND status IN "
                    "('needs_review', 'escalated', 'failed')), 0) AS urgent_open "
                    "FROM inquiries"
                ).fetchone()
                depth = int(row["queued"])
                counts = {name: int(row[name]) for name in counts}
        except sqlite3.Error:
            database = "error"
        worker: PipelineWorker | None = app.state.worker
        cached: tuple[health.Check, health.Check, str] | None = app.state.checks
        if cached is None:
            model_part = ComponentStatus(status="not_checked")
            kb_part = ComponentStatus(status="not_checked")
        else:
            model_part = ComponentStatus(status=cached[0].status, reason=cached[0].reason)
            kb_part = ComponentStatus(status=cached[1].status, reason=cached[1].reason)
        failing = "error" in (database, model_part.status, kb_part.status)
        return StatusResponse(
            status="degraded" if failing else "ok",
            app="citedesk",
            version=__version__,
            synthetic_data=settings.synthetic_data,
            model=settings.llm_model,
            components=Components(
                database=ComponentStatus(status="ok" if database == "ok" else "error"),
                model=model_part,
                knowledge_base=kb_part,
            ),
            queue_depth=depth,
            worker_running=worker is not None and worker.running,
            attention=Attention(**counts),
            checked_at=None if cached is None else cached[2],
        )

    @app.get("/api/status", response_model=StatusResponse)
    def status() -> StatusResponse:
        return build_status()

    @app.post("/api/status/check", response_model=StatusResponse)
    def check_status() -> StatusResponse:
        """Ask the model server and the knowledge base now (short, loopback only, no text sent)."""
        with ThreadPoolExecutor(max_workers=2) as pool:
            model_job = pool.submit(health.check_model, settings, get_json)
            kb_job = pool.submit(health.check_knowledge_base, settings, get_json)
            app.state.checks = (model_job.result(), kb_job.result(), utc_now())
        return build_status()

    @app.get("/api/settings", response_model=SettingsView)
    def read_settings() -> SettingsView:
        """What is in force, read-only. The escalation rules are fixed in code (D-050)."""
        details = business
        if details is None:
            try:
                details = load_business(settings.business_facts_path)
            except (OSError, ValueError):
                details = None
        return SettingsView(
            business=None
            if details is None
            else BusinessOut(
                name=details.name,
                phone=details.phone,
                emergency_phone=details.emergency_phone,
                email=details.email,
            ),
            draft_max_words=settings.draft_max_words,
            model=settings.llm_model,
            synthetic_data=settings.synthetic_data,
            rules=[
                RuleOut(
                    code=code,
                    enabled=settings.escalate_on_low_confidence
                    if code is ReasonCode.LOW_CONFIDENCE
                    else True,
                    set_by="environment" if code is ReasonCode.LOW_CONFIDENCE else "code",
                )
                for code in ReasonCode
            ],
        )

    @app.post("/api/inquiries", status_code=201, response_model=SubmitResponse)
    def create_inquiry(payload: NewInquiry) -> SubmitResponse:
        with db() as conn:
            result = intake.submit(conn, payload, settings)
        wake_worker()
        return SubmitResponse(
            id=result.id,
            status=result.status,
            duplicate_of=result.duplicate_of,
            sensitive_data_masked=result.sensitive_data_masked,
        )

    @app.post("/api/inquiries/import", response_model=ImportResponse)
    async def import_inquiries(request: Request) -> ImportResponse:
        media = request.headers.get("content-type", "").split(";")[0].strip().lower()
        if media in JSONL_TYPES:
            parser = intake.parse_jsonl
        elif media == "text/csv":
            parser = intake.parse_csv
        else:
            raise ApiError(
                415,
                "unsupported_media_type",
                "Send JSONL (application/x-ndjson) or CSV (text/csv).",
            )
        raw = await request.body()
        if len(raw) > MAX_IMPORT_BYTES:
            raise ApiError(
                413, "payload_too_large", f"The file is larger than {MAX_IMPORT_BYTES} bytes."
            )
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise ApiError(400, "invalid_encoding", "The file is not valid UTF-8 text.") from None
        try:
            records = parser(text)
        except ImportFormatError as error:
            reason = IMPORT_REASONS.get(error.code, "the file could not be read")
            raise ApiError(
                400, "invalid_import", f"The file could not be used: {reason}."
            ) from None

        def run() -> intake.ImportSummary:
            with db() as conn:
                return intake.import_records(conn, records, settings)

        summary = await run_in_threadpool(run)
        wake_worker()
        return ImportResponse(
            created=summary.created,
            already_imported=summary.already_imported,
            linked_duplicates=summary.linked_duplicates,
            rejected=[RejectionOut(line=r.line, code=r.code) for r in summary.rejected],
            ids=summary.ids,
        )

    @app.get("/api/inquiries", response_model=InquiryList)
    def list_inquiries(
        status: Annotated[list[InquiryStatus] | None, Query()] = None,
        route: Annotated[list[Route] | None, Query()] = None,
        urgency: Annotated[list[Urgency] | None, Query()] = None,
        q: Annotated[str | None, Query(max_length=200)] = None,
        limit: Annotated[int, Query(ge=1, le=200)] = 50,
        cursor: str | None = None,
    ) -> InquiryList:
        after = decode_cursor(cursor) if cursor else None
        with db() as conn:
            rows = repo.search_inquiries(
                conn,
                statuses=status,
                routes=route,
                urgencies=urgency,
                q=q,
                limit=limit + 1,
                after=after,
            )
        page = rows[:limit]
        with db() as conn:
            summaries = repo.latest_summaries(conn, [i.id for i in page])
        return InquiryList(
            items=[
                InquirySummary(
                    id=i.id,
                    external_id=i.external_id,
                    channel=i.channel,
                    received_at=i.received_at,
                    sender_name=i.sender_name,
                    subject=i.subject,
                    summary=summaries.get(i.id),
                    status=i.status,
                    route=i.route,
                    urgency=i.urgency,
                    primary_intent=i.primary_intent,
                    duplicate_of=i.duplicate_of,
                    is_synthetic=i.is_synthetic,
                )
                for i in page
            ],
            next_cursor=encode_cursor(page[-1]) if len(rows) > limit else None,
        )

    def detail_of(conn: sqlite3.Connection, inquiry_id: int) -> InquiryDetail:
        inquiry = repo.get_inquiry(conn, inquiry_id)
        if inquiry is None:
            raise ApiError(404, "not_found", "No inquiry has that id.")
        draft = repo.latest_draft(conn, inquiry_id)
        return InquiryDetail(
            inquiry=inquiry,
            screening=repo.get_screening(conn, inquiry_id),
            classification=repo.latest_classification(conn, inquiry_id),
            extraction=repo.latest_extraction(conn, inquiry_id),
            escalations=repo.list_escalations(conn, inquiry_id),
            retrievals=repo.list_retrievals(conn, inquiry_id),
            draft=draft,
            checks=repo.list_draft_checks(conn, draft.id) if draft else [],
            history=events.list_events(conn, inquiry_id),
            duplicates=repo.list_duplicates_of(conn, inquiry_id),
        )

    @app.get("/api/inquiries/{inquiry_id}", response_model=InquiryDetail)
    def inquiry_detail(inquiry_id: int) -> InquiryDetail:
        with db() as conn:
            return detail_of(conn, inquiry_id)

    # --- review ---

    @app.post("/api/drafts/{draft_id}/approve", response_model=InquiryDetail)
    def approve_draft(draft_id: int, request: Request, body: ApproveBody) -> InquiryDetail:
        with db() as conn:
            decision = review.approve(
                conn,
                draft_id,
                edited_body=body.edited_body,
                review_seconds=body.review_seconds,
                request_id=request_id_of(request),
            )
            return detail_of(conn, decision.inquiry_id)

    @app.post("/api/drafts/{draft_id}/reject", response_model=InquiryDetail)
    def reject_draft(draft_id: int, request: Request, body: RejectBody) -> InquiryDetail:
        with db() as conn:
            decision = review.reject(
                conn,
                draft_id,
                reason=body.reason,
                review_seconds=body.review_seconds,
                request_id=request_id_of(request),
            )
            return detail_of(conn, decision.inquiry_id)

    @app.post("/api/inquiries/{inquiry_id}/escalate", response_model=InquiryDetail)
    def escalate_inquiry(inquiry_id: int, request: Request, body: EscalateBody) -> InquiryDetail:
        with db() as conn:
            review.escalate(conn, inquiry_id, note=body.note, request_id=request_id_of(request))
            return detail_of(conn, inquiry_id)

    @app.post("/api/inquiries/{inquiry_id}/resolve", response_model=InquiryDetail)
    def resolve_inquiry(inquiry_id: int, request: Request, body: ResolveBody) -> InquiryDetail:
        with db() as conn:
            review.resolve(conn, inquiry_id, note=body.note, request_id=request_id_of(request))
            return detail_of(conn, inquiry_id)

    @app.post("/api/drafts/{draft_id}/redraft", response_model=InquiryDetail)
    def redraft_draft(draft_id: int, request: Request, body: RedraftBody) -> InquiryDetail:
        if llm is None or business is None:
            raise ApiError(503, "model_unavailable", "Redrafting needs the model, which is off.")
        with db() as conn:
            pipeline.redraft_stage(
                conn,
                draft_id,
                body.guidance,
                settings,
                llm,
                business,
                request_id=request_id_of(request),
            )
            draft = repo.get_draft(conn, draft_id)
            return detail_of(conn, draft.inquiry_id if draft else 0)

    @app.post("/api/inquiries/{inquiry_id}/reprocess", response_model=InquiryDetail)
    def reprocess_inquiry(inquiry_id: int, request: Request) -> InquiryDetail:
        with db() as conn:
            pipeline.retry_failed(conn, inquiry_id, request_id=request_id_of(request))
            detail = detail_of(conn, inquiry_id)
        wake_worker()
        return detail

    @app.get("/api/drafts/{draft_id}/export", response_model=ExportText)
    def read_export(draft_id: int) -> ExportText:
        with db() as conn:
            text = review.approved_text(conn, draft_id)
        return ExportText(
            inquiry_id=text.inquiry_id, draft_id=text.draft_id, subject=text.subject, body=text.body
        )

    @app.post("/api/drafts/{draft_id}/export", response_model=ExportText)
    def record_export(draft_id: int, request: Request) -> ExportText:
        with db() as conn:
            text = review.export(conn, draft_id, request_id=request_id_of(request))
        return ExportText(
            inquiry_id=text.inquiry_id, draft_id=text.draft_id, subject=text.subject, body=text.body
        )

    @app.get("/api/insights", response_model=Insights)
    def read_insights() -> Insights:
        with db() as conn:
            return insights.compute(conn, synthetic_data=settings.synthetic_data)

    return app
