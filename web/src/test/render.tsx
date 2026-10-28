import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { App } from "../App";
import type { ApiClient } from "../api/client";
import { ApiProvider } from "../api/context";
import type { StatusResponse } from "../api/types";

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

/** A client whose answers a test controls. Anything a test does not set up fails loudly. */
export function fakeClient(over: Partial<ApiClient> = {}): ApiClient {
  const unexpected = (name: string) => () => {
    throw new Error(`the test did not expect ${name}()`);
  };
  return {
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
