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

/** The state shown on a queue row: what is waiting, in the words a person uses. */
export function stateWords(
  inquiryStatus: Schemas["InquiryStatus"],
  inquiryRoute: Schemas["Route"] | null,
): string {
  if (inquiryStatus === "needs_review") {
    return inquiryRoute === "request_details" ? route.request_details : route.draft_reply;
  }
  return status[inquiryStatus];
}

export const queue = {
  title: "Queue",
  searchLabel: "Search inquiries",
  searchHint: "Searches names, subjects and messages",
  filtersLabel: "Show",
  tabs: {
    review: "Needs review",
    escalated: "Escalated",
    failed: "Failed",
    archived: "Archived",
    all: "All",
  },
  urgentOnly: "Urgent only",
  urgentOnlyClear: "Show everything",
  loading: "Loading the queue",
  empty: "Nothing waiting. New inquiries will appear here.",
  emptyArchived: "Nothing has been archived.",
  noResults: "No inquiries match this filter.",
  showAll: "Show all",
  showMore: "Show more",
  loadingMore: "Loading more…",
  moreFailed: "Couldn't load more. Try again.",
  unknownSender: "Unknown sender",
  noSubject: "(no subject)",
  repeat: "Repeat of an earlier message",
  listLabel: "Inquiries",
  newInquiries: (count: number): string =>
    count === 1 ? "1 new inquiry" : `${count} new inquiries`,
} as const;

export const sentiment: Words<Schemas["Sentiment"]> = {
  positive: "Positive",
  neutral: "Neutral",
  negative: "Unhappy",
  angry: "Angry",
};

export const confidence: Words<Schemas["Confidence"]> = {
  high: "sure",
  medium: "fairly sure",
  low: "not sure",
};

export const service: Words<Schemas["ServiceType"]> = {
  emergency_repair: "Emergency repair",
  drain_cleaning: "Drain cleaning",
  leak_repair: "Leak repair",
  sewer_line_repair: "Sewer line repair",
  water_heater: "Water heater",
  fixture_installation: "Fixture installation",
  inspection: "Inspection",
  other: "Other work",
  unknown: "Not stated",
};

export const property: Words<Schemas["PropertyType"]> = {
  house: "House",
  apartment: "Apartment",
  commercial: "Business premises",
  other: "Other",
  unknown: "Not stated",
};

export const fieldLabel: Words<keyof Schemas["ExtractedFields"]> = {
  service_type: "Service",
  start_date: "Date wanted",
  property_type: "Property",
  address_area: "Area",
  preferred_contact: "Preferred contact",
  booking_reference: "Booking reference",
  dates_as_written: "Date, as written",
};

/** What the draft will ask the customer for, by the name of the missing field. */
export const missingField: Record<string, string> = {
  service_type: "The kind of work",
  start_date: "The date they would like us to visit",
  property_type: "Whether it is a house, an apartment or something else",
  address_area: "The neighbourhood or area",
  booking_reference: "Their booking reference",
};

/** What the pipeline is doing with an inquiry that is not waiting for a person yet. */
export function processingWords(
  inquiryStatus: Schemas["InquiryStatus"],
  hasRetrievals: boolean,
): string {
  switch (inquiryStatus) {
    case "received":
      return "Checking the message";
    case "screened":
      return "Reading the message";
    case "classified":
      return "Deciding what to do";
    case "routed":
      return hasRetrievals ? "Writing a draft" : "Looking up your documents";
    default:
      return "Checking the draft";
  }
}

export const detail = {
  title: "Inquiry",
  back: "Back to the queue",
  jumpToMessage: "Jump to the original message",
  loading: "Loading the inquiry",
  notFound: "No inquiry has that number.",
  sections: {
    understood: "Understood as",
    draft: "Draft reply",
    checks: "Checks",
    sources: "Sources",
    message: "Original message",
    history: "History",
  },
  message: {
    from: "From",
    channel: "Received by",
    masked: "A card or ID number was removed from this message before it was stored.",
    repeatOf: "A repeat of an earlier message:",
    alsoSent: "The same message was also sent as:",
    injection: "This message tries to give instructions to the system.",
  },
  understood: {
    notRead: "The model has not read this message.",
    notReadInjection: "It was not shown to the model because it tries to give it instructions.",
    wants: "Wants",
    urgency: "Urgency",
    tone: "Tone",
    found: "Found in the message",
    notStated: "Not stated",
    missing: "Missing, so the draft asks for",
    nothingMissing: "Nothing is missing.",
    route: "What happens next",
    reasons: "Why it needs you",
  },
  draft: {
    subject: "Subject",
    body: "Reply",
    words: (count: number, limit: number): string =>
      count > limit ? `${count} words. The limit is ${limit}.` : `${count} of ${limit} words`,
    editNote: "Edits are not checked again. You are the check.",
    facts: "Facts in this draft",
    kind: {
      reply: "Written from your documents",
      request_details: "Asks the customer for details",
      holding_reply: "A holding reply. It does not answer the question.",
    },
    forReference: "For reference, not checked for sending",
  },
  checks: {
    failed: "Needs attention",
    warning: "Worth a look",
    passed: "Passed",
    none: "The checks have not run.",
  },
  sources: {
    none: "No passages were used.",
    expand: "Show the whole passage",
    collapse: "Show less",
    open: (n: number): string => `Open source ${n}`,
    heading: (n: number): string => `Source ${n}`,
    page: (page: number): string => `page ${page}`,
  },
  actions: {
    saving: "Saving your decision…",
    undoIn: (seconds: number): string => `Saved in ${seconds} seconds unless you undo.`,
    failed: "Your decision was not saved. Your edit is kept.",
    reasonLabel: "Why are you rejecting it?",
    reasonRequired: "Say why, so the next draft can be better.",
    noteLabel: "What should the owner know?",
    noteRequired: "Add a note for the owner.",
    resolveNote: "Note (optional)",
    send: "Reject draft",
    sendEscalate: "Send to the owner",
    cancel: "Cancel",
  },
  processing: {
    title: "Being prepared",
    body: "This page updates by itself when the draft is ready.",
  },
  failed: {
    title: "This inquiry stopped",
    at: (stage: string): string => `It failed while ${stage}.`,
    retryHint: "Retry restarts it from the step that failed. Nothing was sent.",
  },
  escalated: {
    title: "This needs you",
    body: "A person has to handle this one. Citedesk has not replied to the customer.",
    resolveHint: "When you have dealt with it outside Citedesk, mark it resolved.",
  },
  blocked: {
    title: "Not ready to send",
    body: "The draft failed a check that must pass. It cannot be approved.",
  },
  refusal: {
    title: "The documents don't cover this question",
    body: "Citedesk will not answer from memory. A person has to answer this one.",
    holding: "A holding reply was written. It promises an answer and gives none.",
  },
  rejected: {
    title: "Draft rejected",
    body: "Ask for a new draft, or close this inquiry without a reply.",
    guidanceLabel: "What should the new draft do differently?",
    guidanceRequired: "Say what to change.",
    redraft: "Write a new draft",
    writing: "Writing a new draft. This can take up to a minute.",
    close: "Close without a reply",
  },
  approved: {
    title: "Reply approved",
    subject: "Subject",
    hint: "Copy the reply and paste it into your email. Citedesk does not send it.",
    copyFailed: "Couldn't copy. Select the text above and copy it yourself.",
    copiedTitle: "Copied",
  },
  closed: {
    resolved: "This inquiry was marked resolved.",
    exported: "The reply was copied. Nothing was sent from Citedesk.",
    archived: "This inquiry was archived.",
  },
} as const;

// What a reviewer did. The API sends these as plain codes, so a code with no words here is shown
// as it is rather than dropped.
export const decisionWords: Record<string, string> = {
  approve: "Approved as written",
  edit_approve: "Approved after editing",
  reject: "Rejected",
  escalate: "Sent to the owner",
  resolve: "Marked resolved",
};

export const insights = {
  title: "Insights",
  loading: "Loading the figures",
  empty: "No inquiries yet.",
  summary: (total: number, period: string): string =>
    `${total === 1 ? "1 inquiry" : `${total} inquiries`}${period ? `, ${period}` : ""}.`,
  reviews: "How replies were reviewed",
  asWritten: "Approved as written",
  afterEditing: "Approved after editing",
  shareOf: (approved: number): string =>
    approved === 1 ? "of 1 approved reply" : `of ${approved} approved replies`,
  tooFewShare: (approved: number): string =>
    `Too few approved replies to show a share (${approved} so far)`,
  medianReview: "Median time to review",
  medianDraft: "Median time to draft",
  reviewSample: (n: number): string =>
    n === 1 ? "of 1 reviewed reply" : `of ${n} reviewed replies`,
  draftSample: (n: number): string => (n === 1 ? "of 1 inquiry" : `of ${n} inquiries`),
  fewTimes: (n: number): string => `Only ${n} so far, so treat this as a rough guide`,
  noTimes: "Nothing to measure yet",
  byRoute: "What Citedesk did with each inquiry",
  byDecision: "What reviewers decided",
  byReason: "Why inquiries were escalated",
  noReasons: "No inquiry has been escalated.",
  colWhat: "What",
  colCount: "Inquiries",
  colDecisions: "Decisions",
  colShare: "Share of all",
  saved: {
    title: "Time saved",
    label: "Minutes per inquiry without the tool (your assumption)",
    hint: "Your own number. It stays in this browser and is not sent anywhere.",
    invalid: "Enter a number of minutes, more than 0 and at most 1440.",
    needsReview: "Needs at least one reviewed reply to work out.",
    result: (saved: string): string => `About ${saved} saved.`,
    basis: (replies: number, without: string, median: string): string =>
      `Estimate based on your assumption: ${replies} approved ${replies === 1 ? "reply" : "replies"} × (${without} without the tool − ${median} median review).`,
  },
} as const;
