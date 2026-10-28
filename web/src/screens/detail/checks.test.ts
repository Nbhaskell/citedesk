import { describe, expect, it } from "vitest";
import type { CheckCode, DraftCheck } from "../../api/types";
import { blockedNotice, describeChecks, groundedFigures, ungroundedFigures } from "./checks";

const check = (
  code: CheckCode,
  passed: boolean,
  detail: DraftCheck["detail"],
  blocking = true,
): DraftCheck => ({
  id: 1,
  draft_id: 1,
  check_code: code,
  blocking,
  passed,
  detail,
  created_at: "2026-10-28T12:00:00Z",
});

describe("describeChecks", () => {
  it("puts failed blocking checks first, then failed warnings, then passes", () => {
    const views = describeChecks([
      check("FIGURES_GROUNDED", true, { grounded: ["$149"] }),
      check(
        "STRUCTURE",
        false,
        { missing: ["greeting"], words: 10, max_words: 200, jargon: [] },
        false,
      ),
      check("NO_COMMITMENT", false, { matched_patterns: ["refund_promise"] }),
    ]);
    expect(views.map((v) => v.code)).toEqual(["NO_COMMITMENT", "STRUCTURE", "FIGURES_GROUNDED"]);
  });

  it("says in plain words what the figure check found", () => {
    const [view] = describeChecks([
      check("FIGURES_GROUNDED", false, {
        ungrounded: ["$85"],
        derived: ["$170"],
        grounded: ["$60"],
      }),
    ]);
    expect(view?.title).toBe("Prices and dates match your documents");
    expect(view?.lines).toEqual([
      "Not in your documents: $85",
      "Added up from your documents, so check the sum: $170",
    ]);
  });

  it("lists the figures that were found when the check passed", () => {
    const [view] = describeChecks([check("FIGURES_GROUNDED", true, { grounded: ["$149"] })]);
    expect(view?.lines).toEqual(["Found in your documents: $149"]);
  });

  it("explains each of the other checks", () => {
    const views = Object.fromEntries(
      describeChecks([
        check("NO_COMMITMENT", false, { matched_patterns: ["booking_confirmed"] }),
        check(
          "STRUCTURE",
          false,
          { missing: ["greeting", "sign_off"], words: 250, max_words: 200, jargon: ["source 2"] },
          false,
        ),
        check("CLAIMS_HAVE_SOURCES", false, { bad_indices: [4], no_claims: true }, false),
        check("NO_INJECTION_ECHO", false, {
          system_prompt_echo: true,
          injection_patterns: ["ignore"],
          foreign_links: ["http://evil.example"],
        }),
      ]).map((v) => [v.code, v.lines]),
    );
    expect(views["NO_COMMITMENT"]).toEqual(["Promises found: booking confirmed"]);
    expect(views["STRUCTURE"]).toEqual([
      "No greeting at the start",
      "No sign-off at the end",
      "250 words; the limit is 200",
      "Wording from the system: source 2",
    ]);
    expect(views["CLAIMS_HAVE_SOURCES"]).toEqual([
      "A fact points to a passage that does not exist",
      "The draft states facts but names no passage",
    ]);
    expect(views["NO_INJECTION_ECHO"]).toEqual([
      "Repeats the system's own instructions",
      "Contains wording that tries to give instructions",
      "Links that are not in your documents: http://evil.example",
    ]);
  });

  it("does not show a check that is not implemented, and survives a missing detail", () => {
    const views = describeChecks([
      check("ADDRESSES_ASK", true, null, false),
      check("STRUCTURE", true, null, false),
    ]);
    expect(views.map((v) => v.code)).toEqual(["STRUCTURE"]);
    expect(views[0]?.lines).toEqual([]);
  });
});

describe("figures", () => {
  const checks = [check("FIGURES_GROUNDED", false, { ungrounded: ["$85"], grounded: ["$60"] })];

  it("separates the figures to mark in the draft from those to mark in a passage", () => {
    expect(ungroundedFigures(checks)).toEqual(["$85"]);
    expect(groundedFigures(checks)).toEqual(["$60"]);
  });

  it("finds nothing to mark in a draft whose figures all passed", () => {
    expect(ungroundedFigures([check("FIGURES_GROUNDED", true, { grounded: ["$60"] })])).toEqual([]);
  });

  it("ignores a detail of the wrong shape", () => {
    expect(ungroundedFigures([check("FIGURES_GROUNDED", false, { ungrounded: "$85" })])).toEqual(
      [],
    );
  });
});

describe("blockedNotice", () => {
  it("names the figure that is not in the documents", () => {
    expect(blockedNotice([check("FIGURES_GROUNDED", false, { ungrounded: ["$85"] })])).toBe(
      "Not ready: $85 isn't in your documents.",
    );
    expect(
      blockedNotice([check("FIGURES_GROUNDED", false, { ungrounded: ["$85", "Nov 6"] })]),
    ).toBe("Not ready: $85, Nov 6 aren't in your documents.");
  });

  it("uses the brief's wording for a promise and for copied instructions", () => {
    expect(blockedNotice([check("NO_COMMITMENT", false, { matched_patterns: ["refund"] })])).toBe(
      "Not ready: The draft makes a promise only you can make.",
    );
    expect(blockedNotice([check("NO_INJECTION_ECHO", false, {})])).toContain("Not ready:");
  });

  it("says nothing when nothing blocks", () => {
    expect(blockedNotice([check("FIGURES_GROUNDED", true, {})])).toBeNull();
    expect(blockedNotice([check("STRUCTURE", false, {}, false)])).toBeNull();
  });
});
