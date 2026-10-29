import { describe, expect, it } from "vitest";
import type { InquiryDetail, InquiryStatus } from "../../api/types";
import { detailFixture } from "../../test/render";
import { failedBlockingChecks, pickVariant } from "./variant";

const withStatus = (status: InquiryStatus, over: Partial<InquiryDetail> = {}): InquiryDetail => {
  const base = detailFixture();
  return { ...base, inquiry: { ...base.inquiry, status }, ...over };
};

const failing = (code: "FIGURES_GROUNDED" | "STRUCTURE", blocking: boolean) => {
  const base = detailFixture();
  return base.checks.map((c) => (c.check_code === code ? { ...c, passed: false, blocking } : c));
};

const escalation = (code: "NOT_IN_KNOWLEDGE_BASE" | "HEALTH_SAFETY", resolved = false) => ({
  id: 1,
  inquiry_id: 1,
  reason_code: code,
  detail: null,
  source: "rule" as const,
  resolved,
  resolved_at: null,
  created_at: "2026-10-28T12:00:00Z",
});

describe("pickVariant", () => {
  it.each(["received", "screened", "classified", "routed", "drafted"] as const)(
    "%s is still being prepared",
    (status) => {
      expect(pickVariant(withStatus(status))).toBe("processing");
    },
  );

  it.each([
    ["failed", "failed"],
    ["needs_review", "review"],
    ["rejected", "rejected"],
    ["approved", "approved"],
    ["exported", "closed"],
    ["resolved", "closed"],
    ["archived", "closed"],
  ] as const)("%s is %s", (status, variant) => {
    expect(pickVariant(withStatus(status))).toBe(variant);
  });

  it("an escalation with a failed blocking check is blocked", () => {
    const detail = withStatus("escalated", { checks: failing("FIGURES_GROUNDED", true) });
    expect(pickVariant(detail)).toBe("blocked");
    expect(failedBlockingChecks(detail).map((c) => c.check_code)).toEqual(["FIGURES_GROUNDED"]);
  });

  it("a failed warning does not block", () => {
    const detail = withStatus("escalated", {
      checks: failing("STRUCTURE", false),
      escalations: [escalation("HEALTH_SAFETY")],
    });
    expect(pickVariant(detail)).toBe("escalated");
  });

  it("a knowledge-base decline is a refusal, even though its holding reply has no checks", () => {
    const detail = withStatus("escalated", {
      checks: [],
      escalations: [escalation("NOT_IN_KNOWLEDGE_BASE")],
      draft: { ...detailFixture().draft!, kind: "holding_reply", status: "blocked" },
    });
    expect(pickVariant(detail)).toBe("refusal");
  });

  it("an escalation for any other reason is plainly escalated", () => {
    expect(
      pickVariant(withStatus("escalated", { escalations: [escalation("HEALTH_SAFETY")] })),
    ).toBe("escalated");
  });

  it("a refusal that was already resolved is not a refusal", () => {
    const detail = withStatus("escalated", {
      escalations: [escalation("NOT_IN_KNOWLEDGE_BASE", true)],
    });
    expect(pickVariant(detail)).toBe("escalated");
  });

  it("a failed check beats a refusal reason", () => {
    const detail = withStatus("escalated", {
      checks: failing("FIGURES_GROUNDED", true),
      escalations: [escalation("NOT_IN_KNOWLEDGE_BASE")],
    });
    expect(pickVariant(detail)).toBe("blocked");
  });
});
