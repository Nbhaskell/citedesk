// The only place the app talks to the network. Screens depend on the `ApiClient` interface, so
// tests hand them a fake and nothing in the test suite touches a server.
//
// Errors carry the API's own message and request number, never the request or the response body
// (those hold customer text).
import type {
  ApiErrorBody,
  ExportText,
  InquiryDetail,
  InquiryList,
  InquiryStatus,
  Insights,
  SettingsView,
  StatusResponse,
  Urgency,
} from "./types";

export class ApiError extends Error {
  readonly httpStatus: number;
  readonly code: string;
  readonly requestId: string | null;

  constructor(httpStatus: number, code: string, message: string, requestId: string | null) {
    super(message);
    this.name = "ApiError";
    this.httpStatus = httpStatus;
    this.code = code;
    this.requestId = requestId;
  }

  /** True when the server could not be reached at all (as opposed to answering with an error). */
  get unreachable(): boolean {
    return this.httpStatus === 0;
  }
}

/** What the queue can ask for. Free text goes in `q`; it is sent as a query parameter. */
export interface InquiryQuery {
  status?: InquiryStatus[];
  urgency?: Urgency[];
  q?: string;
  cursor?: string;
  limit?: number;
}

export interface ApproveBody {
  edited_body?: string;
  review_seconds?: number;
}

export interface RejectBody {
  reason: string;
  review_seconds?: number;
}

/**
 * Every call the screens make. A decision answers with the updated inquiry, so a screen replaces
 * what it shows with one object. Nothing here sends a message to a customer: there is no such call.
 */
export interface ApiClient {
  listInquiries(query: InquiryQuery, signal?: AbortSignal): Promise<InquiryList>;
  inquiry(id: number, signal?: AbortSignal): Promise<InquiryDetail>;
  approve(draftId: number, body: ApproveBody): Promise<InquiryDetail>;
  reject(draftId: number, body: RejectBody): Promise<InquiryDetail>;
  redraft(draftId: number, body: { guidance: string }): Promise<InquiryDetail>;
  escalate(inquiryId: number, body: { note: string }): Promise<InquiryDetail>;
  resolve(inquiryId: number, body: { note?: string }): Promise<InquiryDetail>;
  reprocess(inquiryId: number): Promise<InquiryDetail>;
  /** Delete the inquiry and everything stored about it, for good (D-101). */
  deleteInquiry(inquiryId: number): Promise<void>;
  /** The approved text; changes nothing. */
  exportText(draftId: number, signal?: AbortSignal): Promise<ExportText>;
  /** Record that the approved text was copied; the inquiry becomes "exported". */
  recordExport(draftId: number): Promise<ExportText>;
  /** Counts and times only; no customer text. */
  insights(signal?: AbortSignal): Promise<Insights>;
  settings(signal?: AbortSignal): Promise<SettingsView>;
  status(signal?: AbortSignal): Promise<StatusResponse>;
  checkStatus(): Promise<StatusResponse>;
}

type FetchFn = typeof fetch;

function isErrorBody(value: unknown): value is ApiErrorBody {
  if (typeof value !== "object" || value === null || !("error" in value)) return false;
  const error = (value as { error: unknown }).error;
  return (
    typeof error === "object" &&
    error !== null &&
    typeof (error as { code?: unknown }).code === "string" &&
    typeof (error as { message?: unknown }).message === "string"
  );
}

export function queryString(query: InquiryQuery): string {
  const params = new URLSearchParams();
  for (const value of query.status ?? []) params.append("status", value);
  for (const value of query.urgency ?? []) params.append("urgency", value);
  if (query.q) params.set("q", query.q);
  if (query.cursor) params.set("cursor", query.cursor);
  if (query.limit) params.set("limit", String(query.limit));
  const text = params.toString();
  return text ? `?${text}` : "";
}

interface RequestOptions {
  signal?: AbortSignal;
  body?: unknown;
}

export function createHttpClient(fetchFn: FetchFn = fetch, base = ""): ApiClient {
  async function request<T>(
    method: "GET" | "POST" | "DELETE",
    path: string,
    { signal, body }: RequestOptions = {},
  ): Promise<T> {
    const headers: Record<string, string> = { Accept: "application/json" };
    if (body !== undefined) headers["Content-Type"] = "application/json";
    let response: Response;
    try {
      response = await fetchFn(`${base}${path}`, {
        method,
        headers,
        body: body === undefined ? undefined : JSON.stringify(body),
        signal,
        // A decision sent as the page is being left must still arrive.
        keepalive: method !== "GET",
      });
    } catch (error) {
      if (error instanceof Error && error.name === "AbortError") throw error;
      throw new ApiError(0, "network", "Can't reach Citedesk.", null);
    }
    const requestId = response.headers.get("X-Request-ID");
    let parsed: unknown = null;
    try {
      parsed = await response.json();
    } catch {
      parsed = null;
    }
    if (!response.ok) {
      if (isErrorBody(parsed)) {
        throw new ApiError(response.status, parsed.error.code, parsed.error.message, requestId);
      }
      throw new ApiError(
        response.status,
        `http_${response.status}`,
        "The server could not handle that request.",
        requestId,
      );
    }
    return parsed as T;
  }

  const inquiry = (id: number) => `/api/inquiries/${id}`;
  const draft = (id: number) => `/api/drafts/${id}`;

  return {
    listInquiries: (query, signal) =>
      request<InquiryList>("GET", `/api/inquiries${queryString(query)}`, { signal }),
    inquiry: (id, signal) => request<InquiryDetail>("GET", inquiry(id), { signal }),
    approve: (id, body) => request<InquiryDetail>("POST", `${draft(id)}/approve`, { body }),
    reject: (id, body) => request<InquiryDetail>("POST", `${draft(id)}/reject`, { body }),
    redraft: (id, body) => request<InquiryDetail>("POST", `${draft(id)}/redraft`, { body }),
    escalate: (id, body) => request<InquiryDetail>("POST", `${inquiry(id)}/escalate`, { body }),
    resolve: (id, body) => request<InquiryDetail>("POST", `${inquiry(id)}/resolve`, { body }),
    reprocess: (id) => request<InquiryDetail>("POST", `${inquiry(id)}/reprocess`),
    deleteInquiry: async (id) => {
      await request<null>("DELETE", inquiry(id));
    },
    exportText: (id, signal) => request<ExportText>("GET", `${draft(id)}/export`, { signal }),
    recordExport: (id) => request<ExportText>("POST", `${draft(id)}/export`),
    insights: (signal) => request<Insights>("GET", "/api/insights", { signal }),
    settings: (signal) => request<SettingsView>("GET", "/api/settings", { signal }),
    status: (signal) => request<StatusResponse>("GET", "/api/status", { signal }),
    checkStatus: () => request<StatusResponse>("POST", "/api/status/check"),
  };
}
