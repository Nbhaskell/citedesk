import type { DraftCheck, InquiryDetail } from "../../api/types";

/** Which screen the inquiry gets, decided from the data and nothing else (UI plan section 4.2). */
export type Variant =
  | "processing"
  | "failed"
  | "blocked"
  | "refusal"
  | "escalated"
  | "review"
  | "rejected"
  | "approved"
  | "closed";

/** Blocking checks the draft failed. A draft with any of these can never be approved. */
export function failedBlockingChecks(detail: InquiryDetail): DraftCheck[] {
  return detail.checks.filter((check) => check.blocking && !check.passed);
}

export function pickVariant(detail: InquiryDetail): Variant {
  switch (detail.inquiry.status) {
    case "received":
    case "screened":
    case "classified":
    case "routed":
    case "drafted":
      return "processing";
    case "failed":
      return "failed";
    case "escalated": {
      // A holding reply is stored with no checks, so "blocked" is decided by a failed check, not
      // by the draft's own status.
      if (failedBlockingChecks(detail).length > 0) return "blocked";
      const open = detail.escalations.filter((e) => !e.resolved);
      return open.some((e) => e.reason_code === "NOT_IN_KNOWLEDGE_BASE") ? "refusal" : "escalated";
    }
    case "needs_review":
      return "review";
    case "rejected":
      return "rejected";
    case "approved":
      return "approved";
    case "exported":
    case "resolved":
    case "archived":
      return "closed";
  }
}
