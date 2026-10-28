import { describe, expect, it } from "vitest";
import * as copy from "./index";

function strings(value: unknown): string[] {
  if (typeof value === "string") return [value];
  if (typeof value === "function") return [];
  if (value && typeof value === "object") return Object.values(value).flatMap(strings);
  return [];
}

describe("copy", () => {
  it("shows no internal code to the person", () => {
    const wordLists = [
      copy.urgency,
      copy.route,
      copy.status,
      copy.reason,
      copy.reasonFromCheck,
      copy.check,
      copy.intent,
      copy.actions,
    ].flatMap(strings);
    expect(wordLists.length).toBeGreaterThan(40);
    for (const text of wordLists) {
      expect(text, text).not.toMatch(/[a-z]_[a-z]/);
      expect(text, text).not.toMatch(/\b[A-Z]{2,}_[A-Z_]+\b/);
    }
  });

  it("uses the wording the brief fixes", () => {
    expect(copy.reason.NOT_IN_KNOWLEDGE_BASE).toBe("The documents don't cover this question");
    expect(copy.reason.LOW_CONFIDENCE).toBe("Not sure what the customer wants");
    expect(copy.route.request_details).toBe("Asking for details");
    expect(copy.actions.approve.button).toBe("Approve reply");
    expect(copy.actions.approve.done).toBe("Reply approved");
  });

  it("words a reason by where it came from", () => {
    expect(copy.reasonWords("POLICY_EXCEPTION_REQUEST", "rule")).toBe(
      "Asks for an exception only you can grant",
    );
    expect(copy.reasonWords("POLICY_EXCEPTION_REQUEST", "check")).toBe(
      "The draft makes a promise only you can make",
    );
    expect(copy.reasonWords("HEALTH_SAFETY", "check")).toBe(copy.reason.HEALTH_SAFETY);
  });

  it("starts every sentence with a capital and ends none of the labels with a full stop", () => {
    for (const text of strings([copy.reason, copy.check, copy.route, copy.status])) {
      expect(text[0], text).toBe(text[0]?.toUpperCase());
      expect(text, text).not.toMatch(/\.$/);
    }
  });

  it("says nothing is sent and that the data is invented", () => {
    expect(copy.app.demoData).toBe("Demo data. All customers and messages are invented.");
    expect(copy.app.nothingSent).toMatch(/^Nothing is sent from Citedesk/);
  });
});
