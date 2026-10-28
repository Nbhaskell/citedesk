import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { App } from "../App";
import type { ApiClient } from "../api/client";
import { ApiProvider } from "../api/context";
import type { InquirySummary, StatusResponse } from "../api/types";

export function statusFixture(over: Partial<StatusResponse> = {}): StatusResponse {
  return {
    status: "ok",
    app: "citedesk",
    version: "0.0.0",
    synthetic_data: true,
    model: "qwen3:8b",
    components: {
      database: { status: "ok", reason: null },
      model: { status: "not_checked", reason: null },
      knowledge_base: { status: "not_checked", reason: null },
    },
    queue_depth: 0,
    worker_running: true,
    attention: { needs_review: 0, escalated: 0, failed: 0, urgent_open: 0 },
    checked_at: null,
    ...over,
  };
}

export function inquiryFixture(over: Partial<InquirySummary> = {}): InquirySummary {
  return {
    id: 1,
    external_id: null,
    channel: "web_form",
    received_at: new Date(Date.now() - 4 * 60_000).toISOString(),
    sender_name: "Priya S.",
    subject: "Kitchen drain, how much?",
    summary: "Asks how much clearing a kitchen drain costs.",
    status: "needs_review",
    route: "draft_reply",
    urgency: "normal",
    primary_intent: "pricing_question",
    duplicate_of: null,
    is_synthetic: true,
    ...over,
  };
}

/** A client whose answers a test controls. Anything a test does not set up fails loudly. */
export function fakeClient(over: Partial<ApiClient> = {}): ApiClient {
  const unexpected = (name: string) => () => {
    throw new Error(`the test did not expect ${name}()`);
  };
  return {
    listInquiries: async () => ({ items: [], next_cursor: null }),
    status: async () => statusFixture(),
    checkStatus: unexpected("checkStatus"),
    ...over,
  };
}

export function renderApp(client: ApiClient, path = "/") {
  return render(
    <ApiProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    </ApiProvider>,
  );
}
