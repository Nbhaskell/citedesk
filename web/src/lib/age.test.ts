import { describe, expect, it } from "vitest";
import { ageText, exactText } from "./age";

const NOW = Date.parse("2026-10-28T12:00:00Z");
const ago = (seconds: number) => new Date(NOW - seconds * 1000).toISOString();

describe("ageText", () => {
  it.each([
    [0, "just now"],
    [59, "just now"],
    [60, "1 min ago"],
    [4 * 60 + 30, "4 min ago"],
    [59 * 60, "59 min ago"],
    [3600, "1 h ago"],
    [23 * 3600, "23 h ago"],
    [86400, "1 day ago"],
    [3 * 86400, "3 days ago"],
    [29 * 86400, "29 days ago"],
  ])("%i seconds is %s", (seconds, expected) => {
    expect(ageText(ago(seconds), NOW)).toBe(expected);
  });

  it("gives the date once it is more than a month old", () => {
    expect(ageText("2026-05-01T09:00:00Z", NOW)).toBe("1 May 2026");
  });

  it("treats a time in the future (clock skew) as just now", () => {
    expect(ageText(new Date(NOW + 5000).toISOString(), NOW)).toBe("just now");
  });

  it("says nothing for a value that is not a date", () => {
    expect(ageText("not a date", NOW)).toBe("");
    expect(exactText("not a date")).toBe("");
  });

  it("gives an exact time for the tooltip", () => {
    expect(exactText("2026-10-28T12:00:00Z")).toMatch(/28 Oct 2026/);
  });
});
