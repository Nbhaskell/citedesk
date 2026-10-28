// Every string the staff member reads that is not the customer's or the model's own words.
// One module, so wording is reviewed in one place (docs/UI_DESIGN_PLAN.md section 7). Keys for
// values the backend defines are typed from the generated schema: a new code is a compile error
// here until it has words.
import type { components } from "../api/schema";

type Schemas = components["schemas"];
type Words<K extends string> = Record<K, string>;

export const app = {
  name: "Citedesk",
  demoData: "Demo data. All customers and messages are invented.",
  skipToContent: "Skip to the main content",
  nothingSent: "Nothing is sent from Citedesk. Paste this into your email.",
} as const;

export const nav = {
  queue: "Queue",
  insights: "Insights",
  settings: "Settings",
  label: "Main",
} as const;

export const connection = {
  lost: "Connection lost. Retrying.",
  restored: "Connection restored.",
} as const;

export const errors = {
  unreachable: "Can't reach Citedesk. Check that it is running on port 8100.",
  requestId: "Request number",
  retry: "Retry",
  notFoundTitle: "That page does not exist",
  notFoundBody: "Go back to the queue to find what you were looking for.",
  backToQueue: "Back to the queue",
} as const;

export const urgentChip = {
  some: (count: number): string => `Urgent ${count}`,
  none: "No urgent items",
  label: (count: number): string =>
    count === 1
      ? "1 urgent inquiry waiting. Show it."
      : `${count} urgent inquiries waiting. Show them.`,
} as const;

export const urgency: Words<Schemas["Urgency"]> = {
  urgent: "Urgent",
  high: "High",
  normal: "Normal",
  low: "Low",
};

export const route: Words<Schemas["Route"]> = {
  draft_reply: "Draft ready",
  request_details: "Asking for details",
  escalate: "Escalated",
  archive: "Archived",
};

export const status: Words<Schemas["InquiryStatus"]> = {
  received: "Waiting to be read",
  screened: "Reading the message",
  classified: "Deciding what to do",
  routed: "Looking up your documents",
  drafted: "Checking the draft",
  needs_review: "Draft ready",
  escalated: "Escalated",
  approved: "Reply approved",
  rejected: "Draft rejected",
  exported: "Copied",
  resolved: "Resolved",
  archived: "Archived",
  failed: "Failed",
};

// The reason shown for an escalation. Two codes mean different things depending on where they
// came from (D-039, D-041, D-046), so those two have a second wording for a draft check.
export const reason: Words<Schemas["ReasonCode"]> = {
  HEALTH_SAFETY: "Mentions a gas smell, flooding or another safety risk",
  COMPLAINT: "The customer is unhappy with our service",
  REFUND_OR_DISPUTE: "Asks for money back or disputes a charge",
  LEGAL_THREAT: "Mentions a lawyer, a lawsuit or a formal complaint",
  POLICY_EXCEPTION_REQUEST: "Asks for an exception only you can grant",
  INJECTION_SUSPECTED: "This message tries to give instructions to the system",
  LOW_CONFIDENCE: "Not sure what the customer wants",
  NOT_IN_KNOWLEDGE_BASE: "The documents don't cover this question",
  UNVERIFIED_FIGURE: "A price or date in the draft isn't in your documents",
  MANUAL: "Sent to you by a reviewer",
};

export const reasonFromCheck: Partial<Words<Schemas["ReasonCode"]>> = {
  POLICY_EXCEPTION_REQUEST: "The draft makes a promise only you can make",
  INJECTION_SUSPECTED:
    "The draft repeats instructions or contains a link that isn't in your documents",
};

export function reasonWords(
  code: Schemas["ReasonCode"],
  source: Schemas["EscalationSource"],
): string {
  return (source === "check" ? reasonFromCheck[code] : undefined) ?? reason[code];
}

export const check: Words<Schemas["CheckCode"]> = {
  FIGURES_GROUNDED: "Prices and dates match your documents",
  NO_COMMITMENT: "No promises only you can make",
  CLAIMS_HAVE_SOURCES: "Every fact points to a passage",
  STRUCTURE: "Reads like a reply (greeting, sign-off, length)",
  NO_INJECTION_ECHO: "No copied instructions or unknown links",
  ADDRESSES_ASK: "Answers what the customer asked",
};

export const intent: Words<Schemas["Intent"]> = {
  pricing_question: "Pricing question",
  availability_question: "Availability question",
  booking_request: "Booking request",
  booking_change: "Change to a booking",
  cancellation: "Cancellation",
  policy_question: "Policy question",
  service_question: "Question about our services",
  complaint: "Complaint",
  health_or_safety: "Health or safety",
  billing_question: "Billing question",
  partnership_or_sales: "Partnership or sales",
  spam: "Spam",
  other: "Something else",
};

// Buttons name their consequence; the confirmation uses the same words (brief section 6).
export const actions = {
  approve: { button: "Approve reply", done: "Reply approved" },
  approveEdited: { button: "Save edits and approve", done: "Reply approved with your edits" },
  reject: { button: "Reject draft…", done: "Draft rejected" },
  escalate: { button: "Escalate to owner…", done: "Sent to the owner" },
  redraft: { button: "Redraft with guidance…", done: "New draft ready" },
  resolve: { button: "Mark resolved", done: "Marked resolved" },
  copy: { button: "Copy reply", done: "Copied. Nothing was sent." },
  retry: { button: "Retry", done: (stage: string): string => `Retrying from ${stage}` },
  undo: "Undo",
} as const;
