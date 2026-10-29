import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { InquiryDetail } from "../../api/types";
import { inState } from "../../test/detail";
import { fakeClient, detailFixture, inquiryFixture, renderApp } from "../../test/render";
import { markViewed } from "../queue/returnFocus";

beforeEach(() => vi.useFakeTimers({ shouldAdvanceTime: true }));
afterEach(() => {
  vi.useRealTimers();
  window.localStorage.clear();
});

const setup = () => userEvent.setup({ advanceTimers: (ms) => vi.advanceTimersByTime(ms) });

/** Three inquiries, 1 to 3, in the queue and as details of their own. */
function listClient() {
  const items = [1, 2, 3].map((id) =>
    inquiryFixture({ id, sender_name: `Sender ${id}`, summary: `Summary ${id}` }),
  );
  const inquiry = vi.fn(async (id: number): Promise<InquiryDetail> => {
    const base = detailFixture();
    return {
      ...base,
      inquiry: { ...base.inquiry, id },
      draft: base.draft ? { ...base.draft, id: 10 + id, inquiry_id: id } : null,
      checks: base.checks.map((check) => ({ ...check, draft_id: 10 + id })),
    };
  });
  return {
    client: fakeClient({ listInquiries: async () => ({ items, next_cursor: null }), inquiry }),
    inquiry,
  };
}

const title = (id: number) => screen.findByRole("heading", { name: `Inquiry ${id}` });
const focusedRow = () => document.activeElement?.getAttribute("data-id");

/** Start on the queue and open the first inquiry the way a person does. */
async function openFromQueue(user: ReturnType<typeof setup>) {
  const { client } = listClient();
  renderApp(client, "/");
  await user.click(await screen.findByRole("link", { name: /Sender 1/ }));
  await title(1);
  await screen.findByRole("button", { name: "Approve reply" });
}

describe("Detail: j and k through the list it was opened from", () => {
  it("says where this one is in the list, and offers the ones either side", async () => {
    const user = setup();
    await openFromQueue(user);
    const nav = screen.getByRole("navigation", { name: "Other inquiries in your list" });
    expect(within(nav).getByText("1 of 3 in your list")).toBeInTheDocument();
    expect(within(nav).getByRole("link", { name: "Next" })).toHaveAttribute("href", "/inquiries/2");
    expect(within(nav).queryByRole("link", { name: "Previous" })).not.toBeInTheDocument();
  });

  it("moves to the next with j and back with k, and stops at the ends", async () => {
    const user = setup();
    await openFromQueue(user);
    await user.keyboard("k"); // already first
    expect(screen.getByRole("heading", { name: "Inquiry 1" })).toBeInTheDocument();

    await user.keyboard("j");
    await title(2);
    expect(screen.getByText("2 of 3 in your list")).toBeInTheDocument();
    await user.keyboard("j");
    await title(3);
    await user.keyboard("j"); // already last
    expect(screen.getByRole("heading", { name: "Inquiry 3" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Next" })).not.toBeInTheDocument();

    await user.keyboard("k");
    await title(2);
  });

  it("says where it landed to a screen reader", async () => {
    const user = setup();
    await openFromQueue(user);
    await user.keyboard("j");
    await title(2);
    expect(await screen.findByText("Inquiry 2, 2 of 3 in your list")).toBeInTheDocument();
  });

  it("also moves with the Next and Previous links", async () => {
    const user = setup();
    await openFromQueue(user);
    await user.click(screen.getByRole("link", { name: "Next" }));
    await title(2);
    await user.click(screen.getByRole("link", { name: "Previous" }));
    await title(1);
  });

  it("goes back to the queue in one Escape however far it moved, with focus on the last row", async () => {
    const user = setup();
    await openFromQueue(user);
    await user.keyboard("j");
    await title(2);
    await user.keyboard("j");
    await title(3);
    await user.keyboard("{Escape}");
    expect(await screen.findByRole("heading", { name: "Queue" })).toBeInTheDocument();
    await screen.findByRole("link", { name: /Sender 3/ });
    expect(focusedRow()).toBe("3");
  });

  it("offers nothing when the page was opened without a list", async () => {
    const user = setup();
    renderApp(listClient().client, "/inquiries/2");
    await title(2);
    await screen.findByRole("button", { name: "Approve reply" });
    await user.keyboard("j");
    expect(screen.getByRole("heading", { name: "Inquiry 2" })).toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: "Other inquiries in your list" })).toBeNull();
  });

  it.each([
    ["ids that are not numbers", { queue: ["2", "3"] }],
    ["a list that does not contain this inquiry", { queue: [7, 8, 9] }],
    ["something else altogether", "go to 9"],
  ])("ignores %s in the page's state", async (_name, state) => {
    const user = setup();
    renderApp(listClient().client, "/inquiries/1", state);
    await title(1);
    await screen.findByRole("button", { name: "Approve reply" });
    await user.keyboard("j");
    expect(screen.getByRole("heading", { name: "Inquiry 1" })).toBeInTheDocument();
  });

  it("ignores j and k while typing in the reply", async () => {
    const user = setup();
    await openFromQueue(user);
    await user.type(screen.getByLabelText("Reply"), "jk");
    expect(screen.getByRole("heading", { name: "Inquiry 1" })).toBeInTheDocument();
    expect(screen.getByLabelText("Reply")).toHaveValue(
      `${(detailFixture().draft as { body: string }).body}jk`,
    );
  });

  it("ignores them when shortcuts are switched off, though the links still work", async () => {
    window.localStorage.setItem("citedesk.shortcuts", "off");
    const user = setup();
    await openFromQueue(user);
    await user.keyboard("j");
    expect(screen.getByRole("heading", { name: "Inquiry 1" })).toBeInTheDocument();
    await user.click(screen.getByRole("link", { name: "Next" }));
    await title(2);
  });

  it("does not move away from a decision that is waiting to be undone", async () => {
    const user = setup();
    await openFromQueue(user);
    await user.click(screen.getByRole("button", { name: "Approve reply" }));
    await user.keyboard("j");
    await act(async () => vi.advanceTimersByTimeAsync(200));
    expect(screen.getByRole("heading", { name: "Inquiry 1" })).toBeInTheDocument();
    expect(screen.getByText(/Saved in \d seconds unless you undo/)).toBeInTheDocument();
  });

  it("does not move away from a form that is open", async () => {
    const user = setup();
    await openFromQueue(user);
    await user.keyboard("r");
    screen.getByRole("button", { name: "Approve reply" }).focus(); // out of the box, form still open
    await user.keyboard("j");
    expect(screen.getByRole("heading", { name: "Inquiry 1" })).toBeInTheDocument();
    expect(screen.getByLabelText(/Why are you rejecting/)).toBeInTheDocument();
  });
});

describe("Detail: a page that has a form in it", () => {
  it.each([
    ["escalated", () => inState("escalated")],
    ["rejected", () => inState("rejected")],
  ])(
    "does not take focus into the %s form on arrival, so j, k and Escape work",
    async (_n, make) => {
      const user = setup();
      const { client } = listClient();
      const first = client.inquiry;
      client.inquiry = async (id, signal) => ({
        ...(await first(id, signal)),
        inquiry: { ...make().inquiry, id },
      });
      renderApp(client, "/");
      await user.click(await screen.findByRole("link", { name: /Sender 1/ }));
      await title(1);
      await screen.findByRole("textbox");
      await act(async () => {});
      expect(document.activeElement?.tagName).not.toBe("TEXTAREA");

      await user.keyboard("j");
      await title(2);
      await user.keyboard("{Escape}");
      expect(await screen.findByRole("heading", { name: "Queue" })).toBeInTheDocument();
    },
  );

  it("still takes focus into a form the person opened", async () => {
    const user = setup();
    await openFromQueue(user);
    await user.keyboard("r");
    expect(screen.getByLabelText(/Why are you rejecting/)).toHaveFocus();
  });
});

describe("Queue: coming back to the row", () => {
  it("puts focus on the row of the inquiry that was last open", async () => {
    markViewed(2);
    renderApp(listClient().client, "/");
    await screen.findByRole("link", { name: /Sender 2/ });
    await waitFor(() => expect(focusedRow()).toBe("2"));
  });

  it("does so once, and not for an inquiry that is not in the list", async () => {
    markViewed(99);
    renderApp(listClient().client, "/");
    await screen.findByRole("link", { name: /Sender 2/ });
    await act(async () => {});
    expect(focusedRow()).toBeNull();
  });

  it("leaves focus alone when the person has already moved it", async () => {
    markViewed(2);
    const { client } = listClient();
    let release: () => void = () => {};
    const gate = new Promise<void>((resolve) => (release = resolve));
    const slow = fakeClient({
      ...client,
      listInquiries: async (query, signal) => {
        await gate;
        return client.listInquiries(query, signal);
      },
    });
    renderApp(slow, "/");
    const search = await screen.findByLabelText("Search inquiries");
    search.focus();
    release();
    await screen.findByRole("link", { name: /Sender 2/ });
    await act(async () => {});
    expect(search).toHaveFocus();
  });

  it("starts with nothing focused on a first visit", async () => {
    renderApp(listClient().client, "/");
    await screen.findByRole("link", { name: /Sender 1/ });
    await act(async () => {}); // let the focus effect run before saying nothing happened
    expect(focusedRow()).toBeNull();
  });
});

describe("Detail: the wait to undo is announced once, not every second", () => {
  it("announces the wait in the live region, and the ticking bar is not a live region", async () => {
    const user = setup();
    await openFromQueue(user);
    await user.click(screen.getByRole("button", { name: "Approve reply" }));

    expect(
      await screen.findByText(
        "Reply approved, saving in 5 seconds. Press Escape or choose Undo to take it back.",
      ),
    ).toBeInTheDocument();
    await act(async () => vi.advanceTimersByTimeAsync(2100));
    expect(screen.getByText(/Saved in 3 seconds unless you undo/)).toBeInTheDocument();
    const live = screen.getAllByRole("status").map((region) => region.textContent);
    expect(live.some((text) => /Saved in/.test(text ?? ""))).toBe(false);
  });
});
