import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../../api/client";
import type { Insights } from "../../api/types";
import { expectAccessible } from "../../test/axe";
import { counts, fakeClient, insightsFixture, renderApp } from "../../test/render";

function insightsClient(load: () => Promise<Insights> = async () => insightsFixture()) {
  const insights = vi.fn(load);
  return { client: fakeClient({ insights }), insights };
}

const table = (name: string) => screen.getByRole("table", { name });
const rowText = (name: string, row: string) =>
  within(within(table(name)).getByRole("row", { name: new RegExp(row) })).getAllByRole("cell");

beforeEach(() => window.localStorage.clear());
afterEach(() => window.localStorage.clear());

describe("Insights: loading", () => {
  it("says it is loading and shows no figures", async () => {
    const { client } = insightsClient(() => new Promise(() => {}));
    const { container } = renderApp(client, "/insights");
    expect(screen.getByRole("heading", { name: "Insights" })).toBeInTheDocument();
    expect(screen.getByText("Loading the figures")).toBeInTheDocument();
    expect(container.querySelector("[aria-busy='true']")).not.toBeNull();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    await expectAccessible(container);
  });
});

describe("Insights: empty", () => {
  it("says no inquiries have come in, and offers no empty tables", async () => {
    const { client } = insightsClient(async () =>
      insightsFixture({ total_inquiries: 0, period_start: null, period_end: null }),
    );
    const { container } = renderApp(client, "/insights");
    expect(await screen.findByText("No inquiries yet.")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    await expectAccessible(container);
  });
});

describe("Insights: error", () => {
  it("says it cannot reach Citedesk and tries again on request", async () => {
    let fail = true;
    const { client, insights } = insightsClient(async () => {
      if (fail) throw new ApiError(0, "network", "Can't reach Citedesk.", null);
      return insightsFixture();
    });
    const { container } = renderApp(client, "/insights");
    expect(
      await screen.findByText("Can't reach Citedesk. Check that it is running on port 8100."),
    ).toBeInTheDocument();
    await expectAccessible(container);
    fail = false;
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(
      await screen.findByText("41 inquiries, 20 Oct 2026 to 28 Oct 2026."),
    ).toBeInTheDocument();
    expect(insights.mock.calls.length).toBeGreaterThanOrEqual(2);
  });

  it("shows the server's own message and request number", async () => {
    const { client } = insightsClient(async () => {
      throw new ApiError(500, "internal", "Something broke on our side.", "r-77");
    });
    renderApp(client, "/insights");
    expect(await screen.findByText("Something broke on our side.")).toBeInTheDocument();
    expect(screen.getByText("Request number r-77")).toBeInTheDocument();
  });
});

describe("Insights: figures", () => {
  it("shows every figure with its sample and the period", async () => {
    const { client } = insightsClient();
    const { container } = renderApp(client, "/insights");
    expect(
      await screen.findByText("41 inquiries, 20 Oct 2026 to 28 Oct 2026."),
    ).toBeInTheDocument();

    const written = screen.getByRole("group", { name: "Approved as written" });
    expect(within(written).getByText("75%")).toBeInTheDocument();
    expect(within(written).getByText("of 20 approved replies")).toBeInTheDocument();
    const edited = screen.getByRole("group", { name: "Approved after editing" });
    expect(within(edited).getByText("25%")).toBeInTheDocument();

    const review = screen.getByRole("group", { name: "Median time to review" });
    expect(within(review).getByText("1 min 35 s")).toBeInTheDocument();
    expect(within(review).getByText("of 20 reviewed replies")).toBeInTheDocument();
    const draft = screen.getByRole("group", { name: "Median time to draft" });
    expect(within(draft).getByText("12 seconds")).toBeInTheDocument();
    expect(within(draft).getByText("of 33 inquiries")).toBeInTheDocument();
    await expectAccessible(container);
  });

  it("lists what Citedesk did and what reviewers decided, in plain words, zeros included", async () => {
    const { client } = insightsClient();
    renderApp(client, "/insights");
    await screen.findByText("41 inquiries, 20 Oct 2026 to 28 Oct 2026.");

    const routeName = "What Citedesk did with each inquiry";
    expect(rowText(routeName, "Draft ready").map((c) => c.textContent)).toEqual(["28", "68%"]);
    expect(rowText(routeName, "Archived").map((c) => c.textContent)).toEqual(["2", "5%"]);

    const decisionName = "What reviewers decided";
    expect(rowText(decisionName, "Approved as written")[0]).toHaveTextContent("15");
    expect(rowText(decisionName, "Rejected")[0]).toHaveTextContent("3");
    expect(rowText(decisionName, "Marked resolved")[0]).toHaveTextContent("0");
  });

  it("lists only the reasons that happened, most common first, in plain words", async () => {
    const { client } = insightsClient();
    renderApp(client, "/insights");
    await screen.findByText("41 inquiries, 20 Oct 2026 to 28 Oct 2026.");
    const rows = within(table("Why inquiries were escalated")).getAllByRole("row");
    // header, then the two reasons that have a count
    expect(rows).toHaveLength(3);
    expect(rows[1]).toHaveTextContent("Mentions a gas smell, flooding or another safety risk");
    expect(rows[1]).toHaveTextContent("3");
    expect(rows[2]).toHaveTextContent("The documents don't cover this question");
    expect(screen.queryByText("Asks for money back or disputes a charge")).not.toBeInTheDocument();
  });

  it("says so when nothing has been escalated, instead of an empty table", async () => {
    const { client } = insightsClient(async () => insightsFixture({ escalations_by_reason: [] }));
    renderApp(client, "/insights");
    expect(await screen.findByText("No inquiry has been escalated.")).toBeInTheDocument();
    expect(screen.queryByRole("table", { name: "Why inquiries were escalated" })).toBeNull();
  });

  it("shows a code it has no words for as it is, rather than dropping it", async () => {
    const { client } = insightsClient(async () =>
      insightsFixture({
        decisions: [...insightsFixture().decisions, { code: "future_decision", count: 4 }],
      }),
    );
    renderApp(client, "/insights");
    await screen.findByText("41 inquiries, 20 Oct 2026 to 28 Oct 2026.");
    expect(rowText("What reviewers decided", "future_decision")[0]).toHaveTextContent("4");
  });

  it("names one day when everything arrived on it", async () => {
    const { client } = insightsClient(async () =>
      insightsFixture({
        total_inquiries: 1,
        period_start: "2026-10-28T09:00:00Z",
        period_end: "2026-10-28T09:05:00Z",
      }),
    );
    renderApp(client, "/insights");
    expect(await screen.findByText("1 inquiry, 28 Oct 2026.")).toBeInTheDocument();
  });
});

describe("Insights: too little data", () => {
  const few = () =>
    insightsFixture({
      decisions: counts(["approve", "edit_approve", "reject", "escalate", "resolve"], {
        approve: 3,
        edit_approve: 1,
        reject: 2,
      }),
      approved_unchanged_share: 0.75,
      edited_share: 0.25,
      median_review_seconds: 40,
      review_time_sample: 4,
    });

  it("replaces the shares with how few there are, not a percentage of four", async () => {
    const { client } = insightsClient(async () => few());
    const { container } = renderApp(client, "/insights");
    const written = await screen.findByRole("group", { name: "Approved as written" });
    expect(
      within(written).getByText("Too few approved replies to show a share (4 so far)"),
    ).toBeInTheDocument();
    expect(within(written).queryByText("75%")).not.toBeInTheDocument();
    const edited = screen.getByRole("group", { name: "Approved after editing" });
    expect(within(edited).queryByText("25%")).not.toBeInTheDocument();
    await expectAccessible(container);
  });

  it("still shows the counts, which are facts, and marks a thin median as rough", async () => {
    const { client } = insightsClient(async () => few());
    renderApp(client, "/insights");
    const review = await screen.findByRole("group", { name: "Median time to review" });
    expect(within(review).getByText("40 seconds")).toBeInTheDocument();
    expect(within(review).getByText("of 4 reviewed replies")).toBeInTheDocument();
    expect(
      within(review).getByText("Only 4 so far, so treat this as a rough guide"),
    ).toBeInTheDocument();
    expect(rowText("What reviewers decided", "Approved as written")[0]).toHaveTextContent("3");
  });

  it("shows the shares at exactly ten approved replies", async () => {
    const { client } = insightsClient(async () =>
      insightsFixture({
        decisions: counts(["approve", "edit_approve"], { approve: 7, edit_approve: 3 }),
        approved_unchanged_share: 0.7,
        edited_share: 0.3,
      }),
    );
    renderApp(client, "/insights");
    const written = await screen.findByRole("group", { name: "Approved as written" });
    expect(within(written).getByText("70%")).toBeInTheDocument();
  });

  it("says there is nothing to measure when there is no time yet", async () => {
    const { client } = insightsClient(async () =>
      insightsFixture({
        median_review_seconds: null,
        review_time_sample: 0,
        median_seconds_to_draft: null,
        draft_time_sample: 0,
        decisions: counts(["approve"], {}),
        approved_unchanged_share: null,
        edited_share: null,
      }),
    );
    renderApp(client, "/insights");
    const review = await screen.findByRole("group", { name: "Median time to review" });
    expect(within(review).getByText("Nothing to measure yet")).toBeInTheDocument();
    const draft = screen.getByRole("group", { name: "Median time to draft" });
    expect(within(draft).getByText("Nothing to measure yet")).toBeInTheDocument();
  });
});

describe("Insights: time saved", () => {
  it("works out an estimate from the person's own number and labels it as theirs", async () => {
    const { client } = insightsClient();
    const { container } = renderApp(client, "/insights");
    const input = await screen.findByLabelText(
      "Minutes per inquiry without the tool (your assumption)",
    );
    expect(screen.queryByText(/saved\./)).not.toBeInTheDocument();
    await userEvent.type(input, "10");
    // 20 approved replies x (10 min - 1 min 35 s) = 168 min
    expect(screen.getByText("About 2 h 48 min saved.")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Estimate based on your assumption: 20 approved replies × (10 min without the tool − 1 min 35 s median review).",
      ),
    ).toBeInTheDocument();
    await expectAccessible(container);
  });

  it("keeps the number in this browser and gives it back on the next visit", async () => {
    const first = renderApp(insightsClient().client, "/insights");
    const input = await screen.findByLabelText(
      "Minutes per inquiry without the tool (your assumption)",
    );
    await userEvent.type(input, "12");
    expect(window.localStorage.getItem("citedesk.minutesWithoutTool")).toBe("12");
    first.unmount();

    renderApp(insightsClient().client, "/insights");
    expect(
      await screen.findByLabelText("Minutes per inquiry without the tool (your assumption)"),
    ).toHaveValue("12");
    expect(screen.getByText(/saved\./)).toBeInTheDocument();
  });

  it("forgets it when the box is emptied", async () => {
    window.localStorage.setItem("citedesk.minutesWithoutTool", "12");
    renderApp(insightsClient().client, "/insights");
    const input = await screen.findByLabelText(
      "Minutes per inquiry without the tool (your assumption)",
    );
    await userEvent.clear(input);
    expect(window.localStorage.getItem("citedesk.minutesWithoutTool")).toBeNull();
    expect(screen.queryByText(/saved\./)).not.toBeInTheDocument();
  });

  it("says what is wrong with a number it cannot use, and shows no estimate", async () => {
    const { client } = insightsClient();
    const { container } = renderApp(client, "/insights");
    const input = await screen.findByLabelText(
      "Minutes per inquiry without the tool (your assumption)",
    );
    await userEvent.type(input, "lots");
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(
      screen.getByText("Enter a number of minutes, more than 0 and at most 1440."),
    ).toBeInTheDocument();
    expect(screen.queryByText(/saved\./)).not.toBeInTheDocument();
    await expectAccessible(container);
  });

  it("shows no estimate when no reply has been reviewed, and says why", async () => {
    const { client } = insightsClient(async () =>
      insightsFixture({ median_review_seconds: null, review_time_sample: 0 }),
    );
    renderApp(client, "/insights");
    const input = await screen.findByLabelText(
      "Minutes per inquiry without the tool (your assumption)",
    );
    await userEvent.type(input, "10");
    expect(screen.getByText("Needs at least one reviewed reply to work out.")).toBeInTheDocument();
  });

  it("works when the browser will not keep the number", async () => {
    const setItem = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    try {
      renderApp(insightsClient().client, "/insights");
      const input = await screen.findByLabelText(
        "Minutes per inquiry without the tool (your assumption)",
      );
      await userEvent.type(input, "10");
      expect(screen.getByText(/saved\./)).toBeInTheDocument();
    } finally {
      setItem.mockRestore();
    }
  });
});
