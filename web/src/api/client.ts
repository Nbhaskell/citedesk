// The only place the app talks to the network. Screens depend on the `ApiClient` interface, so
// tests hand them a fake and nothing in the test suite touches a server.
//
// Errors carry the API's own message and request number, never the request or the response body
// (those hold customer text).
import type { ApiErrorBody, InquiryList, InquiryStatus, StatusResponse, Urgency } from "./types";

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

export interface ApiClient {
  listInquiries(query: InquiryQuery, signal?: AbortSignal): Promise<InquiryList>;
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

export function createHttpClient(fetchFn: FetchFn = fetch, base = ""): ApiClient {
  async function request<T>(
    method: "GET" | "POST",
    path: string,
    signal?: AbortSignal,
  ): Promise<T> {
    let response: Response;
    try {
      response = await fetchFn(`${base}${path}`, {
        method,
        headers: { Accept: "application/json" },
        signal,
      });
    } catch (error) {
      if (error instanceof Error && error.name === "AbortError") throw error;
      throw new ApiError(0, "network", "Can't reach Citedesk.", null);
    }
    const requestId = response.headers.get("X-Request-ID");
    let body: unknown = null;
    try {
      body = await response.json();
    } catch {
      body = null;
    }
    if (!response.ok) {
      if (isErrorBody(body)) {
        throw new ApiError(response.status, body.error.code, body.error.message, requestId);
      }
      throw new ApiError(
        response.status,
        `http_${response.status}`,
        "The server could not handle that request.",
        requestId,
      );
    }
    return body as T;
  }

  return {
    listInquiries: (query, signal) =>
      request<InquiryList>("GET", `/api/inquiries${queryString(query)}`, signal),
    status: (signal) => request<StatusResponse>("GET", "/api/status", signal),
    checkStatus: () => request<StatusResponse>("POST", "/api/status/check"),
  };
}
