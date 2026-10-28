import { describe, expect, it } from "vitest";
import type { Retrieval, Source } from "../../api/types";
import { highlight, mergedSources } from "./sources";

const source = (text: string, file = "pricing.md"): Source => ({
  file,
  section: "S",
  page: null,
  text,
});
const retrieval = (declined: boolean, ...sources: Source[]): Retrieval => ({
  id: 1,
  inquiry_id: 1,
  question: "q",
  declined,
  kb_answer: null,
  sources,
  duration_ms: null,
  created_at: "2026-10-28T12:00:00Z",
});

describe("mergedSources", () => {
  it("keeps the order, drops repeats, and skips declined questions", () => {
    const a = source("A");
    const b = source("B");
    const rows = [
      retrieval(false, a, b),
      retrieval(true, source("Declined")),
      retrieval(false, source("A"), source("C")),
    ];
    expect(mergedSources(rows).map((s) => s.text)).toEqual(["A", "B", "C"]);
  });

  it("treats the same text in another file as another passage", () => {
    expect(mergedSources([retrieval(false, source("A"), source("A", "hours.md"))])).toHaveLength(2);
  });

  it("is empty when nothing was answered", () => {
    expect(mergedSources([retrieval(true, source("A"))])).toEqual([]);
    expect(mergedSources([])).toEqual([]);
  });
});

describe("highlight", () => {
  it("marks every occurrence and keeps the rest in between", () => {
    expect(highlight("From $149, or $149 again", ["$149"])).toEqual([
      { text: "From ", marked: false },
      { text: "$149", marked: true },
      { text: ", or ", marked: false },
      { text: "$149", marked: true },
      { text: " again", marked: false },
    ]);
  });

  it("returns the text whole when nothing matches or no needle is given", () => {
    expect(highlight("Plain text", ["$85"])).toEqual([{ text: "Plain text", marked: false }]);
    expect(highlight("Plain text", [])).toEqual([{ text: "Plain text", marked: false }]);
    expect(highlight("Plain text", [""])).toEqual([{ text: "Plain text", marked: false }]);
    expect(highlight("", ["x"])).toEqual([]);
  });

  it("prefers the longer needle where two overlap", () => {
    expect(highlight("Costs $1,490 today", ["$1,490", "$1"])).toEqual([
      { text: "Costs ", marked: false },
      { text: "$1,490", marked: true },
      { text: " today", marked: false },
    ]);
  });

  it("never reads text as markup", () => {
    const segments = highlight('<b>$149</b> "quoted"', ["$149"]);
    expect(segments.map((s) => s.text).join("")).toBe('<b>$149</b> "quoted"');
    expect(segments.find((s) => s.marked)?.text).toBe("$149");
  });

  it("covers text that starts or ends with a match", () => {
    expect(highlight("$85", ["$85"])).toEqual([{ text: "$85", marked: true }]);
  });
});
