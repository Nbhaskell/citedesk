import { describe, expect, it } from "vitest";
import type { AuditEvent } from "../../api/types";
import { describeEvent, historyLines } from "./history";

let next = 1;
const event = (over: Partial<AuditEvent>): AuditEvent => ({
  id: next++,
  inquiry_id: 1,
  event_type: "status_changed",
  stage: null,
  from_status: null,
  to_status: null,
  payload: {},
  request_id: null,
  duration_ms: null,
  created_at: "2026-10-28T12:00:00Z",
  ...over,
});

describe("describeEvent", () => {
  it("describes the moves a reviewer cares about", () => {
    expect(describeEvent(event({ to_status: "escalated" }))).toBe("Escalated");
    expect(describeEvent(event({ to_status: "approved" }))).toBe("Reply approved");
    expect(describeEvent(event({ to_status: "exported" }))).toBe("Reply copied");
  });

  it("leaves ready-for-review to the line that says what the checks found", () => {
    expect(describeEvent(event({ to_status: "needs_review" }))).toBeNull();
    expect(
      describeEvent(
        event({
          event_type: "stage_finished",
          stage: "check",
          payload: { blocking_failed: [], warnings_failed: [] },
        }),
      ),
    ).toBe("Checked: all passed");
    expect(
      describeEvent(
        event({
          event_type: "stage_finished",
          stage: "check",
          payload: { blocking_failed: [], warnings_failed: ["STRUCTURE"] },
        }),
      ),
    ).toBe("Checked: passed, with notes");
  });

  it("describes decisions by their code", () => {
    expect(
      describeEvent(
        event({ event_type: "review_recorded", payload: { decision: "edit_approve" } }),
      ),
    ).toBe("Edited and approved by a reviewer");
    expect(
      describeEvent(event({ event_type: "review_recorded", payload: { decision: "nonsense" } })),
    ).toBeNull();
  });

  it("names a failed check and a failed step in plain words", () => {
    expect(
      describeEvent(event({ event_type: "check_failed", payload: { check: "FIGURES_GROUNDED" } })),
    ).toBe("Check failed: Prices and dates match your documents");
    expect(describeEvent(event({ event_type: "stage_failed", stage: "retrieve" }))).toBe(
      "Failed while looking up your documents",
    );
  });

  it("says a retry was a retry, and from which step", () => {
    expect(
      describeEvent(
        event({
          from_status: "failed",
          to_status: "drafted",
          payload: { retry_of_stage: "check" },
        }),
      ),
    ).toBe("Retried from checking the draft");
  });

  it("marks a redraft", () => {
    expect(
      describeEvent(
        event({
          event_type: "stage_finished",
          stage: "draft",
          payload: { redraft: true, version: 2 },
        }),
      ),
    ).toBe("New draft written");
  });

  it("skips what adds nothing", () => {
    expect(describeEvent(event({ event_type: "stage_started", stage: "draft" }))).toBeNull();
    expect(
      describeEvent(event({ event_type: "route_decided", payload: { route: "draft_reply" } })),
    ).toBeNull();
    expect(describeEvent(event({ event_type: "stage_finished", stage: "retrieve" }))).toBeNull();
  });
});

describe("historyLines", () => {
  it("lists what is worth saying, oldest first", () => {
    const lines = historyLines([
      event({ id: 30, to_status: "approved" }),
      event({ id: 10, to_status: "escalated" }),
      event({ id: 20, event_type: "stage_started" }),
    ]);
    expect(lines.map((l) => l.text)).toEqual(["Escalated", "Reply approved"]);
  });
});
