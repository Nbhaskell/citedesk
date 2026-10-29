import { describe, expect, it } from "vitest";
import { currentTab, parseView, toQuery, viewToSearch } from "./params";

const view = (search: string, q = "") => parseView(new URLSearchParams(search), q);

describe("queue view", () => {
  it("defaults to the needs-review tab", () => {
    expect(toQuery(view(""))).toEqual({ status: ["needs_review"] });
    expect(currentTab(view(""))).toBe("review");
  });

  it.each([
    ["show=escalated", { status: ["escalated"] }],
    ["show=failed", { status: ["failed"] }],
    ["show=archived", { status: ["archived"] }],
    ["show=all", {}],
  ])("%s", (search, expected) => {
    expect(toQuery(view(search))).toEqual(expected);
  });

  it("ignores a filter it does not know", () => {
    expect(toQuery(view("show=everything"))).toEqual({ status: ["needs_review"] });
  });

  it("urgent only covers every state that needs a person", () => {
    expect(toQuery(view("urgency=urgent"))).toEqual({
      status: ["needs_review", "escalated", "failed"],
      urgency: ["urgent"],
    });
    expect(currentTab(view("urgency=urgent"))).toBeNull();
  });

  it("urgent only with a chosen tab narrows that tab", () => {
    expect(toQuery(view("show=escalated&urgency=urgent"))).toEqual({
      status: ["escalated"],
      urgency: ["urgent"],
    });
  });

  it("sends the search text trimmed, and nothing when it is blank", () => {
    expect(toQuery(view("", "  leak  "))).toEqual({ status: ["needs_review"], q: "leak" });
    expect(toQuery(view("", "   "))).toEqual({ status: ["needs_review"] });
  });

  it("writes only codes to the address, and only what differs from the default", () => {
    expect(viewToSearch({ filter: null, urgentOnly: false })).toBe("");
    expect(viewToSearch({ filter: "review", urgentOnly: false })).toBe("");
    expect(viewToSearch({ filter: "failed", urgentOnly: false })).toBe("?show=failed");
    expect(viewToSearch({ filter: null, urgentOnly: true })).toBe("?urgency=urgent");
    expect(viewToSearch({ filter: "all", urgentOnly: true })).toBe("?show=all&urgency=urgent");
  });
});
