import { afterEach, beforeEach, describe, expect, it } from "vitest";
import {
  approvedCount,
  countOf,
  formatDuration,
  formatMinutes,
  loadAssumption,
  MIN_SAMPLE,
  parseMinutes,
  percent,
  periodText,
  saveAssumption,
  savedMinutes,
} from "./figures";

describe("formatDuration", () => {
  it.each([
    [0.2, "under 1 second"],
    [1, "1 second"],
    [45.4, "45 seconds"],
    [60, "1 min"],
    [125, "2 min 5 s"],
    [3600, "1 h"],
    [3900, "1 h 5 min"],
  ])("%s seconds reads %s", (seconds, words) => {
    expect(formatDuration(seconds)).toBe(words);
  });
});

describe("formatMinutes", () => {
  it("rounds to whole minutes and uses hours past an hour", () => {
    expect(formatMinutes(0)).toBe("0 min");
    expect(formatMinutes(12.4)).toBe("12 min");
    expect(formatMinutes(200)).toBe("3 h 20 min");
    expect(formatMinutes(120)).toBe("2 h");
  });
});

describe("percent", () => {
  it("rounds a share to a whole percent", () => {
    expect(percent(0.75)).toBe("75%");
    expect(percent(1 / 3)).toBe("33%");
    expect(percent(0)).toBe("0%");
  });
});

describe("counts", () => {
  const list = [
    { code: "approve", count: 15 },
    { code: "edit_approve", count: 5 },
    { code: "reject", count: 3 },
  ];
  it("finds a count, and zero for a code that is absent", () => {
    expect(countOf(list, "reject")).toBe(3);
    expect(countOf(list, "resolve")).toBe(0);
  });
  it("counts approved replies as unchanged plus edited", () => {
    expect(approvedCount(list)).toBe(20);
  });
  it("shows shares from ten approved replies", () => {
    expect(MIN_SAMPLE).toBe(10);
  });
});

describe("periodText", () => {
  it("names the first and last day, in UTC like the queue's dates", () => {
    expect(periodText("2026-10-20T09:00:00Z", "2026-10-28T11:30:00Z")).toBe(
      "20 Oct 2026 to 28 Oct 2026",
    );
  });
  it("says one day when both ends fall on it", () => {
    expect(periodText("2026-10-28T09:00:00Z", "2026-10-28T11:30:00Z")).toBe("28 Oct 2026");
  });
  it("is empty without a period", () => {
    expect(periodText(null, null)).toBe("");
  });
});

describe("parseMinutes", () => {
  it.each([
    ["12", 12],
    [" 7.5 ", 7.5],
    ["7,5", 7.5],
    ["1440", 1440],
  ])("reads %j as %s", (text, minutes) => {
    expect(parseMinutes(text)).toBe(minutes);
  });
  it.each(["", "abc", "0", "-3", "1441", "Infinity", "1e9", "5 min"])(
    "does not read %j",
    (text) => {
      expect(parseMinutes(text)).toBeNull();
    },
  );
});

describe("savedMinutes", () => {
  it("is replies times what each saved: the assumption less the median review", () => {
    // 20 replies x (10 min - 1.5 min) = 170 min
    expect(savedMinutes(20, 10, 90)).toBeCloseTo(170);
  });
  it("is never negative: a review slower than the assumption saves nothing", () => {
    expect(savedMinutes(20, 1, 600)).toBe(0);
  });
  it("is unknown without a median review time, a reply or an assumption", () => {
    expect(savedMinutes(20, 10, null)).toBeNull();
    expect(savedMinutes(0, 10, 90)).toBeNull();
    expect(savedMinutes(20, null, 90)).toBeNull();
  });
});

describe("the assumption is kept in this browser only", () => {
  beforeEach(() => window.localStorage.clear());
  afterEach(() => window.localStorage.clear());

  it("round-trips the text", () => {
    expect(loadAssumption()).toBe("");
    saveAssumption("12");
    expect(loadAssumption()).toBe("12");
  });
  it("forgets it when emptied", () => {
    saveAssumption("12");
    saveAssumption("");
    expect(window.localStorage.getItem("citedesk.minutesWithoutTool")).toBeNull();
  });
});
