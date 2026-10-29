import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, type ApiClient, type InquiryQuery } from "../../api/client";
import type { InquiryList } from "../../api/types";
import { expectAccessible } from "../../test/axe";
import { fakeClient, inquiryFixture, renderApp, statusFixture } from "../../test/render";

const page = (items = [inquiryFixture()], next_cursor: string | null = null): InquiryList => ({
  items,
  next_cursor,
});

function queueClient(
  list: ApiClient["listInquiries"] = async () => page(),
  over: Partial<ApiClient> = {},
) {
  const listInquiries = vi.fn(list);
  return { client: fakeClient({ listInquiries, ...over }), listInquiries };
}

const lastQuery = (fn: ReturnType<typeof vi.fn>): InquiryQuery =>
  fn.mock.calls[fn.mock.calls.length - 1]?.[0] as InquiryQuery;

afterEach(() => vi.useRealTimers());

describe("Queue: loading", () => {
  it("says it is loading and shows no rows", async () => {
    const { client } = queueClient(() => new Promise(() => {}));
    const { container } = renderApp(client);
    expect(screen.getByText("Loading the queue")).toBeInTheDocument();
    expect(container.querySelector("[aria-busy='true']")).not.toBeNull();
    expect(screen.queryByRole("link", { name: /Priya/ })).not.toBeInTheDocument();
    await expectAccessible(container);
  });
});

describe("Queue: empty", () => {
  it("says nothing is waiting", async () => {
    const { client } = queueClient(async () => page([]));
    const { container } = renderApp(client);
    expect(
      await screen.findByText("Nothing waiting. New inquiries will appear here."),
    ).toBeInTheDocument();
    await expectAccessible(container);
  });

  it("says when nothing has been archived", async () => {
    const { client } = queueClient(async () => page([]));
    renderApp(client, "/?show=archived");
    expect(await screen.findByText("Nothing has been archived.")).toBeInTheDocument();
  });
});

describe("Queue: error", () => {
  it("says it cannot reach Citedesk and retries on request", async () => {
    let fail = true;
    const { client, listInquiries } = queueClient(async () => {
      if (fail) throw new ApiError(0, "network", "Can't reach Citedesk.", null);
      return page();
    });
    const { container } = renderApp(client);
    expect(
      await screen.findByText("Can't reach Citedesk. Check that it is running on port 8100."),
    ).toBeInTheDocument();
    await expectAccessible(container);
    fail = false;
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByRole("link", { name: /Priya S\./ })).toBeInTheDocument();
    expect(listInquiries.mock.calls.length).toBeGreaterThanOrEqual(2);
  });

  it("shows the API's own message and the request number for any other failure", async () => {
    const { client } = queueClient(async () => {
      throw new ApiError(422, "invalid_cursor", "The cursor is not valid.", "req42");
    });
    renderApp(client);
    expect(await screen.findByText("The cursor is not valid.")).toBeInTheDocument();
    expect(screen.getByText("Request number req42")).toBeInTheDocument();
  });
});

describe("Queue: rows", () => {
  it("shows urgency as a word, the state, summary, sender and age, and links to the inquiry", async () => {
    const items = [
      inquiryFixture({
        id: 7,
        urgency: "urgent",
        status: "escalated",
        route: "escalate",
        summary: "Smell of gas in the basement.",
        sender_name: "Dana W.",
        received_at: new Date(Date.now() - 4 * 60_000).toISOString(),
      }),
      inquiryFixture({
        id: 8,
        urgency: "normal",
        route: "request_details",
        summary: "Wants a faucet fitted, no date.",
        sender_name: "Sam O.",
      }),
    ];
    const { client } = queueClient(async () => page(items));
    const { container } = renderApp(client);
    const urgent = await screen.findByRole("link", { name: /Dana W\./ });
    expect(urgent).toHaveAttribute("href", "/inquiries/7");
    expect(within(urgent).getByText("Urgent")).toBeInTheDocument();
    expect(within(urgent).getByText("Escalated")).toBeInTheDocument();
    expect(within(urgent).getByText("Smell of gas in the basement.")).toBeInTheDocument();
    expect(within(urgent).getByText("4 min ago")).toBeInTheDocument();
    const asking = screen.getByRole("link", { name: /Sam O\./ });
    expect(within(asking).getByText("Asking for details")).toBeInTheDocument();
    expect(within(asking).getByText("Normal")).toBeInTheDocument();
    await expectAccessible(container);
  });

  it("shows an unread item without an urgency tag, in plain words", async () => {
    const { client } = queueClient(async () =>
      page([
        inquiryFixture({
          urgency: null,
          status: "received",
          route: null,
          summary: null,
          subject: "Leaking tap",
        }),
      ]),
    );
    renderApp(client);
    const row = await screen.findByRole("link", { name: /Leaking tap/ });
    expect(within(row).getByText("Waiting to be read")).toBeInTheDocument();
    expect(within(row).queryByText(/Urgent|High|Normal|Low/)).not.toBeInTheDocument();
  });

  it("falls back to the subject, then to a stated absence, and marks repeats", async () => {
    const { client } = queueClient(async () =>
      page([
        inquiryFixture({ id: 1, summary: null, subject: "Leaking tap" }),
        inquiryFixture({ id: 2, summary: null, subject: null, sender_name: null, duplicate_of: 1 }),
      ]),
    );
    renderApp(client);
    expect(await screen.findByText("Leaking tap")).toBeInTheDocument();
    expect(screen.getByText("(no subject)")).toBeInTheDocument();
    expect(screen.getByText("Unknown sender")).toBeInTheDocument();
    expect(screen.getByText("Repeat of an earlier message")).toBeInTheDocument();
  });

  it("renders a customer's markup as plain text", async () => {
    const hostile = '<img src="x" onerror="alert(1)"> <b>bold</b> <script>bad()</script>';
    const { client } = queueClient(async () =>
      page([inquiryFixture({ summary: hostile, sender_name: "<i>Eve</i>" })]),
    );
    const { container } = renderApp(client);
    await screen.findByText(hostile);
    expect(screen.getByText("<i>Eve</i>")).toBeInTheDocument();
    expect(container.querySelector("main img, main b, main script, main i")).toBeNull();
  });
});

describe("Queue: filters", () => {
  it("asks for what needs review by default, with the counts on the tabs", async () => {
    const attention = { needs_review: 12, escalated: 3, failed: 1, urgent_open: 0 };
    const { client, listInquiries } = queueClient(undefined, {
      status: async () => statusFixture({ attention }),
    });
    renderApp(client);
    await screen.findByRole("link", { name: /Priya S\./ });
    expect(lastQuery(listInquiries)).toEqual({ status: ["needs_review"] });
    const tabs = screen.getByRole("navigation", { name: "Show" });
    await waitFor(() =>
      expect(within(tabs).getByRole("link", { name: /Escalated 3/ })).toBeVisible(),
    );
    expect(within(tabs).getByRole("link", { name: /Needs review 12/ })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(within(tabs).getByRole("link", { name: /Failed 1/ })).toBeVisible();
  });

  it("asks for the other tabs by their states", async () => {
    const user = userEvent.setup();
    const { client, listInquiries } = queueClient();
    renderApp(client);
    await screen.findByRole("link", { name: /Priya S\./ });
    const tabs = screen.getByRole("navigation", { name: "Show" });
    for (const [name, expected] of [
      ["Escalated", { status: ["escalated"] }],
      ["Failed", { status: ["failed"] }],
      ["Archived", { status: ["archived"] }],
      ["All", {}],
    ] as const) {
      await user.click(within(tabs).getByRole("link", { name: new RegExp(`^${name}`) }));
      await waitFor(() => expect(lastQuery(listInquiries)).toEqual(expected));
      expect(within(tabs).getByRole("link", { name: new RegExp(`^${name}`) })).toHaveAttribute(
        "aria-current",
        "page",
      );
    }
  });

  it("never shows one filter's rows under another while the new ones load", async () => {
    const user = userEvent.setup();
    const { client } = queueClient(async (query) =>
      query.status?.[0] === "escalated" ? new Promise(() => {}) : page(),
    );
    renderApp(client);
    await screen.findByRole("link", { name: /Priya S\./ });
    await user.click(screen.getByRole("link", { name: /^Escalated/ }));
    expect(await screen.findByText("Loading the queue")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Priya S\./ })).not.toBeInTheDocument();
  });

  it("follows the urgent chip: every state that needs a person, urgent only", async () => {
    const user = userEvent.setup();
    const { client, listInquiries } = queueClient();
    renderApp(client, "/?urgency=urgent");
    await screen.findByRole("link", { name: /Priya S\./ });
    expect(lastQuery(listInquiries)).toEqual({
      status: ["needs_review", "escalated", "failed"],
      urgency: ["urgent"],
    });
    expect(screen.getByText("Urgent only")).toBeInTheDocument();
    const tabs = screen.getByRole("navigation", { name: "Show" });
    expect(within(tabs).queryByRole("link", { current: "page" })).toBeNull();
    await user.click(screen.getByRole("button", { name: "Show everything" }));
    await waitFor(() => expect(lastQuery(listInquiries)).toEqual({ status: ["needs_review"] }));
    expect(screen.queryByText("Urgent only")).not.toBeInTheDocument();
  });
});

describe("Queue: search", () => {
  it("sends the text after the person stops typing, trimmed", async () => {
    const user = userEvent.setup();
    const { client, listInquiries } = queueClient();
    renderApp(client);
    await screen.findByRole("link", { name: /Priya S\./ });
    await user.type(screen.getByRole("searchbox", { name: "Search inquiries" }), " leak ");
    await waitFor(() =>
      expect(lastQuery(listInquiries)).toEqual({ status: ["needs_review"], q: "leak" }),
    );
  });

  it("limits what can be typed", () => {
    const { client } = queueClient();
    renderApp(client);
    expect(screen.getByRole("searchbox", { name: "Search inquiries" })).toHaveAttribute(
      "maxlength",
      "200",
    );
  });

  it("says when nothing matches and offers to show everything, clearing the search", async () => {
    const user = userEvent.setup();
    const { client, listInquiries } = queueClient(async (query) => (query.q ? page([]) : page()));
    const { container } = renderApp(client);
    await screen.findByRole("link", { name: /Priya S\./ });
    const box = screen.getByRole("searchbox", { name: "Search inquiries" });
    await user.type(box, "zzz");
    expect(await screen.findByText("No inquiries match this filter.")).toBeInTheDocument();
    await expectAccessible(container);
    await user.click(screen.getByRole("button", { name: "Show all" }));
    await waitFor(() => expect(lastQuery(listInquiries)).toEqual({}));
    expect(box).toHaveValue("");
    expect(await screen.findByRole("link", { name: /Priya S\./ })).toBeInTheDocument();
  });
});

describe("Queue: more rows", () => {
  it("shows more on request and keeps what was already there", async () => {
    const user = userEvent.setup();
    const { client, listInquiries } = queueClient(async (query) =>
      query.cursor
        ? page([inquiryFixture({ id: 2, sender_name: "Marcus L." })], null)
        : page([inquiryFixture({ id: 1, sender_name: "Priya S." })], "c1"),
    );
    renderApp(client);
    await screen.findByRole("link", { name: /Priya S\./ });
    await user.click(screen.getByRole("button", { name: "Show more" }));
    expect(await screen.findByRole("link", { name: /Marcus L\./ })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Priya S\./ })).toBeInTheDocument();
    expect(listInquiries).toHaveBeenCalledWith(
      expect.objectContaining({ cursor: "c1", status: ["needs_review"] }),
    );
    expect(screen.queryByRole("button", { name: "Show more" })).not.toBeInTheDocument();
  });

  it("says when more could not be loaded and lets the person try again", async () => {
    const user = userEvent.setup();
    let fail = true;
    const { client } = queueClient(async (query) => {
      if (query.cursor) {
        if (fail) throw new ApiError(0, "network", "Can't reach Citedesk.", null);
        return page([inquiryFixture({ id: 2, sender_name: "Marcus L." })]);
      }
      return page([inquiryFixture({ id: 1 })], "c1");
    });
    renderApp(client);
    await user.click(await screen.findByRole("button", { name: "Show more" }));
    expect(await screen.findByText("Couldn't load more. Try again.")).toBeInTheDocument();
    fail = false;
    await user.click(screen.getByRole("button", { name: "Show more" }));
    expect(await screen.findByRole("link", { name: /Marcus L\./ })).toBeInTheDocument();
  });
});

describe("Queue: new arrivals", () => {
  it("announces them politely, once, without moving focus", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    let calls = 0;
    const { client } = queueClient(async () => {
      calls += 1;
      return calls === 1
        ? page([inquiryFixture({ id: 1 })])
        : page([inquiryFixture({ id: 1 }), inquiryFixture({ id: 2, sender_name: "New P." })]);
    });
    renderApp(client);
    await screen.findByRole("link", { name: /Priya S\./ });
    const row = screen.getByRole("link", { name: /Priya S\./ });
    row.focus();
    await act(async () => vi.advanceTimersByTimeAsync(5000));
    expect(await screen.findByRole("link", { name: /New P\./ })).toBeInTheDocument();
    const regions = screen.getAllByRole("status");
    expect(regions.some((r) => r.textContent === "1 new inquiry")).toBe(true);
    expect(row).toHaveFocus();
    await act(async () => vi.advanceTimersByTimeAsync(5000));
    expect(regions.filter((r) => r.textContent?.includes("new inquiry"))).toHaveLength(1);
  });

  it("does not announce the first page as new", async () => {
    const { client } = queueClient(async () =>
      page([inquiryFixture({ id: 1 }), inquiryFixture({ id: 2 })]),
    );
    renderApp(client);
    await screen.findAllByRole("link", { name: /Priya S\./ });
    expect(screen.getAllByRole("status").some((r) => /new inquir/.test(r.textContent ?? ""))).toBe(
      false,
    );
  });
});

describe("Queue: keyboard", () => {
  const three = async () =>
    page([1, 2, 3].map((id) => inquiryFixture({ id, sender_name: `Person ${id}` })));

  it("moves through the rows with j and k and stops at the ends", async () => {
    const user = userEvent.setup();
    const { client } = queueClient(three);
    renderApp(client);
    await screen.findByRole("link", { name: /Person 1/ });
    await user.keyboard("j");
    expect(screen.getByRole("link", { name: /Person 1/ })).toHaveFocus();
    await user.keyboard("jj");
    expect(screen.getByRole("link", { name: /Person 3/ })).toHaveFocus();
    await user.keyboard("j");
    expect(screen.getByRole("link", { name: /Person 3/ })).toHaveFocus();
    await user.keyboard("k");
    expect(screen.getByRole("link", { name: /Person 2/ })).toHaveFocus();
    await user.keyboard("kk");
    expect(screen.getByRole("link", { name: /Person 1/ })).toHaveFocus();
  });

  it("opens the focused row with Enter", async () => {
    const user = userEvent.setup();
    const { client } = queueClient(three);
    renderApp(client);
    await screen.findByRole("link", { name: /Person 1/ });
    await user.keyboard("jj{Enter}");
    expect(await screen.findByRole("heading", { name: /^Inquiry 2/ })).toBeInTheDocument();
  });

  it("leaves j and k to the search box while typing", async () => {
    const user = userEvent.setup();
    const { client } = queueClient(three);
    renderApp(client);
    await screen.findByRole("link", { name: /Person 1/ });
    const box = screen.getByRole("searchbox", { name: "Search inquiries" });
    await user.click(box);
    await user.keyboard("jk");
    expect(box).toHaveValue("jk");
    expect(box).toHaveFocus();
  });

  it("does nothing with the shortcuts switched off", async () => {
    window.localStorage.setItem("citedesk.shortcuts", "off");
    const user = userEvent.setup();
    const { client } = queueClient(three);
    renderApp(client);
    await screen.findByRole("link", { name: /Person 1/ });
    await user.keyboard("j");
    expect(screen.getByRole("link", { name: /Person 1/ })).not.toHaveFocus();
    window.localStorage.clear();
  });
});
