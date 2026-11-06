import { render } from "@testing-library/react";
import { MemoryRouter, parsePath } from "react-router-dom";
import { App } from "../App";
import type { ApiClient } from "../api/client";
import { ApiProvider } from "../api/context";
import type {
  InquiryDetail,
  InquirySummary,
  Insights,
  SettingsView,
  StatusResponse,
} from "../api/types";

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

export const DRAFT_BODY =
  "Hi Priya,\n\nThanks for getting in touch. Drain cleaning for one fixture starts at $149.\n\nKind regards,\nKestrel Hollow Plumbing";
export const PASSAGE =
  "Drain cleaning, one fixture (sink, tub, shower or toilet): $149 (starting price)";
const T = "2026-10-28T12:00:00Z";

/** A detail waiting for review: a ready draft, all checks passed, one source. Override per test. */
export function detailFixture(over: Partial<InquiryDetail> = {}): InquiryDetail {
  const base: InquiryDetail = {
    inquiry: {
      id: 1,
      external_id: null,
      channel: "web_form",
      received_at: new Date(Date.now() - 4 * 60_000).toISOString(),
      sender_name: "Priya S.",
      sender_email: "priya@example.com",
      subject: "Kitchen drain, how much?",
      body: "Hi, how much to clear a slow kitchen drain? Can someone come this week?",
      thread_id: null,
      duplicate_of: null,
      status: "needs_review",
      route: "draft_reply",
      urgency: "normal",
      primary_intent: "pricing_question",
      failure_stage: null,
      failure_message: null,
      is_synthetic: true,
      created_at: T,
      updated_at: T,
    },
    screening: {
      id: 1,
      inquiry_id: 1,
      spam_score: 0,
      injection_flags: [],
      sensitive_data_masked: false,
      result: "clean",
      created_at: T,
    },
    classification: {
      id: 1,
      inquiry_id: 1,
      attempt: 1,
      model: "fake",
      prompt_version: "understand-v1",
      intents: [
        { intent: "pricing_question", confidence: "high" },
        { intent: "availability_question", confidence: "medium" },
      ],
      primary_intent: "pricing_question",
      primary_confidence: "high",
      urgency: "normal",
      sentiment: "neutral",
      summary: "Asks how much a kitchen drain costs and if someone can come this week.",
      safety_net_hit: false,
      raw_response: "{}",
      focused_signals: [],
      duration_ms: 1,
      created_at: T,
    },
    extraction: {
      id: 1,
      inquiry_id: 1,
      classification_id: 1,
      fields: {
        service_type: "drain_cleaning",
        start_date: null,
        property_type: "house",
        address_area: null,
        preferred_contact: null,
        booking_reference: null,
        dates_as_written: "this week",
      },
      missing_fields: [],
      created_at: T,
    },
    escalations: [],
    retrievals: [
      {
        id: 1,
        inquiry_id: 1,
        question: "How much does drain cleaning cost?",
        declined: false,
        kb_answer: "It starts at $149.",
        sources: [{ file: "pricing.md", section: "Pricing > Drains", page: null, text: PASSAGE }],
        duration_ms: 1,
        created_at: T,
      },
    ],
    draft: {
      id: 11,
      inquiry_id: 1,
      version: 1,
      kind: "reply",
      subject: "Re: Kitchen drain, how much?",
      body: DRAFT_BODY,
      claims: [{ text: "starts at $149", source_index: 0 }],
      model: "fake",
      prompt_version: "draft-v1",
      guidance: null,
      status: "ready",
      duration_ms: 1,
      created_at: T,
    },
    checks: [
      {
        id: 1,
        draft_id: 11,
        check_code: "FIGURES_GROUNDED",
        blocking: true,
        passed: true,
        detail: { ungrounded: [], derived: [], grounded: ["$149"] },
        created_at: T,
      },
      {
        id: 2,
        draft_id: 11,
        check_code: "NO_COMMITMENT",
        blocking: true,
        passed: true,
        detail: { matched_patterns: [] },
        created_at: T,
      },
      {
        id: 3,
        draft_id: 11,
        check_code: "NO_INJECTION_ECHO",
        blocking: true,
        passed: true,
        detail: { system_prompt_echo: false, injection_patterns: [], foreign_links: [] },
        created_at: T,
      },
      {
        id: 4,
        draft_id: 11,
        check_code: "STRUCTURE",
        blocking: false,
        passed: true,
        detail: { words: 17, max_words: 200, missing: [], jargon: [] },
        created_at: T,
      },
      {
        id: 5,
        draft_id: 11,
        check_code: "CLAIMS_HAVE_SOURCES",
        blocking: false,
        passed: true,
        detail: { bad_indices: [], no_claims: false },
        created_at: T,
      },
    ],
    history: [],
    duplicates: [],
  };
  return { ...base, ...over };
}

export function settingsFixture(over: Partial<SettingsView> = {}): SettingsView {
  return {
    business: {
      name: "Kestrel Hollow Plumbing",
      phone: "555-0171",
      emergency_phone: "555-0172",
      email: "kestrelhollow@example.com",
    },
    draft_max_words: 200,
    model: "qwen3:8b",
    synthetic_data: true,
    rules: REASONS.map((code) => ({
      code: code as SettingsView["rules"][number]["code"],
      enabled: true,
      set_by: code === "LOW_CONFIDENCE" ? "environment" : "code",
    })),
    ...over,
  };
}

const ROUTES = ["draft_reply", "request_details", "escalate", "archive"];
const DECISIONS = ["approve", "edit_approve", "reject", "escalate", "resolve"];
const REASONS = [
  "HEALTH_SAFETY",
  "COMPLAINT",
  "REFUND_OR_DISPUTE",
  "LEGAL_THREAT",
  "POLICY_EXCEPTION_REQUEST",
  "INJECTION_SUSPECTED",
  "LOW_CONFIDENCE",
  "NOT_IN_KNOWLEDGE_BASE",
  "UNVERIFIED_FIGURE",
  "MANUAL",
];

/** Every code with a count, zero for those not named, as the API returns them. */
export function counts(codes: string[], named: Record<string, number> = {}) {
  return codes.map((code) => ({ code, count: named[code] ?? 0 }));
}

/** 41 inquiries, 25 decided: enough that the shares are shown. Override per test. */
export function insightsFixture(over: Partial<Insights> = {}): Insights {
  return {
    total_inquiries: 41,
    by_status: counts(["needs_review", "approved", "exported"], { needs_review: 5, approved: 20 }),
    by_route: counts(ROUTES, { draft_reply: 28, request_details: 6, escalate: 5, archive: 2 }),
    decisions: counts(DECISIONS, { approve: 15, edit_approve: 5, reject: 3, escalate: 2 }),
    escalations_by_reason: counts(REASONS, { HEALTH_SAFETY: 3, NOT_IN_KNOWLEDGE_BASE: 2 }),
    approved_unchanged_share: 0.75,
    edited_share: 0.25,
    median_review_seconds: 95,
    review_time_sample: 20,
    median_seconds_to_draft: 12,
    draft_time_sample: 33,
    period_start: "2026-10-20T09:00:00Z",
    period_end: "2026-10-28T11:30:00Z",
    synthetic_data: true,
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
    inquiry: async () => detailFixture(),
    approve: unexpected("approve"),
    reject: unexpected("reject"),
    redraft: unexpected("redraft"),
    escalate: unexpected("escalate"),
    resolve: unexpected("resolve"),
    reprocess: unexpected("reprocess"),
    exportText: unexpected("exportText"),
    recordExport: unexpected("recordExport"),
    insights: async () => insightsFixture(),
    settings: async () => settingsFixture(),
    status: async () => statusFixture(),
    checkStatus: unexpected("checkStatus"),
    ...over,
  };
}

/** `state` is the router state the page was opened with, as a queue row's link sends it. */
export function renderApp(client: ApiClient, path = "/", state?: unknown) {
  return render(
    <ApiProvider client={client}>
      <MemoryRouter initialEntries={[{ ...parsePath(path), state }]}>
        <App />
      </MemoryRouter>
    </ApiProvider>,
  );
}
