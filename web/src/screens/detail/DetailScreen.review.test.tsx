import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../../api/client";
import type { InquiryDetail } from "../../api/types";
import { detailClient, inState } from "../../test/detail";
import { expectAccessible } from "../../test/axe";
import { DRAFT_BODY, PASSAGE, detailFixture, renderApp, settingsFixture } from "../../test/render";
import { wordCount } from "./draft";

beforeEach(() => vi.useFakeTimers({ shouldAdvanceTime: true }));
afterEach(() => {
  vi.useRealTimers();
  window.localStorage.clear();
});

const setup = () => userEvent.setup({ advanceTimers: (ms) => vi.advanceTimersByTime(ms) });
const wait = (ms: number) => act(async () => vi.advanceTimersByTimeAsync(ms));
const open = async (client: ReturnType<typeof detailClient>["client"]) => {
  const view = renderApp(client, "/inquiries/1");
  await screen.findByRole("heading", { name: "Inquiry 1" });
  await screen.findByRole("button", { name: "Approve reply" });
  return view;
};

const approvedDetail = (): InquiryDetail =>
  inState("approved", { draft: { ...detailFixture().draft!, status: "approved" } });

describe("Detail: a draft waiting for review", () => {
  it("shows the message, what was understood, the draft, its checks and its sources", async () => {
    const { client } = detailClient();
    const { container } = await open(client);

    const message = screen.getByRole("region", { name: "Original message" });
    expect(within(message).getByText(/how much to clear a slow kitchen drain/)).toBeInTheDocument();
    expect(within(message).getByText(/priya@example.com/)).toBeInTheDocument();

    const understood = screen.getByRole("region", { name: "Understood as" });
    expect(
      within(understood).getByText("Pricing question, Availability question (fairly sure)"),
    ).toBeInTheDocument();
    expect(within(understood).getByText("Normal")).toBeInTheDocument();
    expect(within(understood).getByText("Neutral")).toBeInTheDocument();
    expect(within(understood).getByText("Drain cleaning")).toBeInTheDocument();
    expect(within(understood).getByText("House")).toBeInTheDocument();
    expect(within(understood).getByText("this week")).toBeInTheDocument();
    expect(within(understood).getByText("What Citedesk decided")).toBeInTheDocument();
    expect(within(understood).getByText("Write a reply from your documents")).toBeInTheDocument();

    expect(screen.getByLabelText("Reply")).toHaveValue(DRAFT_BODY);
    expect(screen.getByText(/Re: Kitchen drain, how much\?/)).toBeInTheDocument();
    expect(screen.getByText(`${wordCount(DRAFT_BODY)} of 200 words`)).toBeInTheDocument();
    expect(screen.getByText("Edits are not checked again. You are the check.")).toBeInTheDocument();

    const checks = screen.getByRole("region", { name: "Checks" });
    expect(within(checks).getAllByText("Passed")).toHaveLength(5);
    expect(within(checks).getByText("Found in your documents: $149")).toBeInTheDocument();

    const sources = screen.getByRole("region", { name: "Sources (1)" });
    expect(within(sources).getByText(/pricing.md › Pricing > Drains/)).toBeInTheDocument();
    expect(sources.querySelector("mark")?.textContent).toBe("$149");
    await expectAccessible(container);
  });

  it("opens the passage a claim points to", async () => {
    const user = setup();
    const { client } = detailClient();
    await open(client);
    const toggle = screen.getByRole("button", { name: /Show the whole passage/ });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    await user.click(screen.getByRole("button", { name: "Open source 0" }));
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(document.getElementById("source-0")).toHaveTextContent(PASSAGE);
  });

  it("highlights what is missing and says what the draft asks for", async () => {
    const base = detailFixture();
    const { client } = detailClient({
      ...base,
      extraction: { ...base.extraction!, missing_fields: ["start_date", "address_area"] },
    });
    await open(client);
    expect(screen.getByText("Missing, so the draft asks for")).toBeInTheDocument();
    expect(screen.getByText("The date they would like us to visit")).toBeInTheDocument();
    expect(screen.getByText("The neighbourhood or area")).toBeInTheDocument();
  });

  it("warns about a removed card number and links repeats of the message", async () => {
    const base = detailFixture();
    const { client } = detailClient({
      ...base,
      screening: { ...base.screening!, sensitive_data_masked: true },
      inquiry: { ...base.inquiry, duplicate_of: 9 },
      duplicates: [12, 14],
    });
    await open(client);
    expect(screen.getByText(/card or ID number was removed/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "#9" })).toHaveAttribute("href", "/inquiries/9");
    expect(screen.getByRole("link", { name: "#12" })).toHaveAttribute("href", "/inquiries/12");
  });

  it("shows a customer's and the model's markup as plain text", async () => {
    const hostile = '<img src="x" onerror="alert(1)"> <b>bold</b>';
    const base = detailFixture();
    const { client } = detailClient({
      ...base,
      inquiry: { ...base.inquiry, body: hostile, sender_name: "<i>Eve</i>" },
      classification: { ...base.classification!, summary: "<script>bad()</script>" },
    });
    const { container } = await open(client);
    expect(screen.getByText(hostile)).toBeInTheDocument();
    expect(container.querySelector("main img, main b, main i, main script")).toBeNull();
  });

  it("says the draft is over the word limit", async () => {
    const { client } = detailClient();
    const settings = settingsFixture({ draft_max_words: 5 });
    client.settings = async () => settings;
    renderApp(client, "/inquiries/1");
    expect(
      await screen.findByText(`${wordCount(DRAFT_BODY)} words. The limit is 5.`),
    ).toBeInTheDocument();
  });
});

describe("Detail: approving", () => {
  it("waits five seconds where it can be undone, then saves and shows the approved reply", async () => {
    const user = setup();
    const { client, set } = detailClient();
    client.approve = vi.fn(async () => {
      set(approvedDetail());
      return approvedDetail();
    });
    client.exportText = async () => ({
      inquiry_id: 1,
      draft_id: 11,
      subject: "Re: Kitchen drain, how much?",
      body: DRAFT_BODY,
    });
    await open(client);
    await user.click(screen.getByRole("button", { name: "Approve reply" }));
    expect(screen.getByText(/Saved in 5 seconds unless you undo/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Approve reply" })).toBeDisabled();
    expect(client.approve).not.toHaveBeenCalled();
    await wait(4900);
    expect(client.approve).not.toHaveBeenCalled();
    await wait(200);
    expect(client.approve).toHaveBeenCalledTimes(1);
    const [draftId, body] = (client.approve as ReturnType<typeof vi.fn>).mock.calls[0] as [
      number,
      object,
    ];
    expect(draftId).toBe(11);
    expect(body).toHaveProperty("review_seconds");
    expect(body).not.toHaveProperty("edited_body");
    expect(await screen.findByRole("heading", { name: "Reply approved" })).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Copy reply" })).toBeInTheDocument();
  });

  it("sends nothing if it is undone", async () => {
    const user = setup();
    const { client } = detailClient();
    client.approve = vi.fn();
    await open(client);
    await user.click(screen.getByRole("button", { name: "Approve reply" }));
    await user.click(screen.getByRole("button", { name: "Undo" }));
    await wait(10_000);
    expect(client.approve).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Approve reply" })).toBeEnabled();
  });

  it("is undone by Escape, which does not also leave the page", async () => {
    const user = setup();
    const { client } = detailClient();
    client.approve = vi.fn();
    await open(client);
    await user.click(screen.getByRole("button", { name: "Approve reply" }));
    await user.keyboard("{Escape}");
    await wait(10_000);
    expect(client.approve).not.toHaveBeenCalled();
    expect(screen.getByRole("heading", { name: "Inquiry 1" })).toBeInTheDocument();
  });

  it("is sent at once when the person leaves the page", async () => {
    const user = setup();
    const { client } = detailClient();
    client.approve = vi.fn(async () => approvedDetail());
    await open(client);
    await user.click(screen.getByRole("button", { name: "Approve reply" }));
    await user.click(screen.getByRole("link", { name: "Back to the queue" }));
    expect(client.approve).toHaveBeenCalledTimes(1);
  });

  it("sends the person's edit, and the button says so", async () => {
    const user = setup();
    const { client } = detailClient();
    client.approve = vi.fn(async () => approvedDetail());
    await open(client);
    await user.type(screen.getByLabelText("Reply"), " Thanks!");
    const button = screen.getByRole("button", { name: "Save edits and approve" });
    await user.click(button);
    await wait(5100);
    const [, body] = (client.approve as ReturnType<typeof vi.fn>).mock.calls[0] as [
      number,
      { edited_body: string },
    ];
    expect(body.edited_body).toBe(`${DRAFT_BODY} Thanks!`);
  });

  it("keeps the edit and says what happened when saving fails", async () => {
    const user = setup();
    const { client } = detailClient();
    client.approve = vi.fn(async () => {
      throw new ApiError(409, "wrong_state", "This draft is not waiting for a decision.", "req9");
    });
    await open(client);
    await user.type(screen.getByLabelText("Reply"), " Extra");
    await user.click(screen.getByRole("button", { name: "Save edits and approve" }));
    await wait(5100);
    const alert = await screen.findByText(/Your decision was not saved\. Your edit is kept\./);
    expect(alert).toHaveTextContent("Your decision was not saved. Your edit is kept.");
    expect(alert).toHaveTextContent("This draft is not waiting for a decision.");
    expect(alert).toHaveTextContent("req9");
    expect(screen.getByLabelText("Reply")).toHaveValue(`${DRAFT_BODY} Extra`);
    expect(screen.getByRole("button", { name: "Save edits and approve" })).toBeEnabled();
  });

  it("keeps an unsent edit in the browser and brings it back", async () => {
    const user = setup();
    const { client } = detailClient();
    const first = await open(client);
    await user.type(screen.getByLabelText("Reply"), " Saved");
    expect(window.localStorage.getItem("citedesk.draft.11")).toBe(`${DRAFT_BODY} Saved`);
    first.unmount();
    renderApp(client, "/inquiries/1");
    expect(await screen.findByLabelText("Reply")).toHaveValue(`${DRAFT_BODY} Saved`);
  });

  it("forgets the saved edit when the decision lands", async () => {
    const user = setup();
    const { client } = detailClient();
    client.approve = vi.fn(async () => approvedDetail());
    await open(client);
    await user.type(screen.getByLabelText("Reply"), " Saved");
    await user.click(screen.getByRole("button", { name: "Save edits and approve" }));
    await wait(5100);
    await waitFor(() => expect(window.localStorage.getItem("citedesk.draft.11")).toBeNull());
  });
});

describe("Detail: rejecting and escalating", () => {
  it("asks why before rejecting, then waits to be undone", async () => {
    const user = setup();
    const { client, set } = detailClient();
    const rejected = inState("rejected", {
      draft: { ...detailFixture().draft!, status: "rejected" },
    });
    client.reject = vi.fn(async () => {
      set(rejected);
      return rejected;
    });
    await open(client);
    await user.click(screen.getByRole("button", { name: "Reject draft…" }));
    const form = screen.getByLabelText("Why are you rejecting it?");
    expect(form).toHaveFocus();
    await user.click(screen.getByRole("button", { name: "Reject draft" }));
    expect(screen.getByText("Say why, so the next draft can be better.")).toBeInTheDocument();
    expect(client.reject).not.toHaveBeenCalled();
    await user.type(form, "Wrong price");
    await user.click(screen.getByRole("button", { name: "Reject draft" }));
    expect(screen.getByText(/Draft rejected\./)).toBeInTheDocument();
    await wait(5100);
    expect(client.reject).toHaveBeenCalledWith(
      11,
      expect.objectContaining({ reason: "Wrong price" }),
    );
    expect(await screen.findByRole("heading", { name: "Draft rejected" })).toBeInTheDocument();
  });

  it("needs a note to escalate, and sends it at once", async () => {
    const user = setup();
    const { client, set } = detailClient();
    const escalated = inState("escalated", {
      escalations: [
        {
          id: 1,
          inquiry_id: 1,
          reason_code: "MANUAL",
          detail: "Escalated by the reviewer; the note is in the review record.",
          source: "reviewer",
          resolved: false,
          resolved_at: null,
          created_at: "2026-10-28T12:05:00Z",
        },
      ],
    });
    client.escalate = vi.fn(async () => {
      set(escalated);
      return escalated;
    });
    await open(client);
    await user.click(screen.getByRole("button", { name: "Escalate to owner…" }));
    await user.click(screen.getByRole("button", { name: "Send to the owner" }));
    expect(screen.getByText("Add a note for the owner.")).toBeInTheDocument();
    await user.type(screen.getByLabelText("What should the owner know?"), "Owner please");
    await user.click(screen.getByRole("button", { name: "Send to the owner" }));
    expect(client.escalate).toHaveBeenCalledWith(1, { note: "Owner please" });
    expect(await screen.findByRole("heading", { name: "This needs you" })).toBeInTheDocument();
    expect(screen.getAllByText("Sent to you by a reviewer").length).toBeGreaterThan(0);
  });
});

describe("Detail: keyboard", () => {
  it("a approves, e edits, r opens the reject form and x the escalate form", async () => {
    const user = setup();
    const { client } = detailClient();
    client.approve = vi.fn(async () => approvedDetail());
    await open(client);
    await user.keyboard("e");
    expect(screen.getByLabelText("Reply")).toHaveFocus();
    await user.tab({ shift: true });
    await user.keyboard("r");
    expect(screen.getByLabelText("Why are you rejecting it?")).toHaveFocus();
    await user.keyboard("{Escape}");
    expect(screen.queryByLabelText("Why are you rejecting it?")).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Inquiry 1" })).toBeInTheDocument();
    await user.keyboard("x");
    expect(screen.getByLabelText("What should the owner know?")).toHaveFocus();
    await user.keyboard("{Escape}");
    await user.keyboard("a");
    expect(screen.getByText(/Saved in 5 seconds/)).toBeInTheDocument();
  });

  it("leaves the keys to the text while typing", async () => {
    const user = setup();
    const { client } = detailClient();
    client.approve = vi.fn();
    await open(client);
    await user.click(screen.getByLabelText("Reply"));
    await user.keyboard("arx");
    expect(screen.getByLabelText("Reply")).toHaveValue(`${DRAFT_BODY}arx`);
    expect(screen.queryByText(/Saved in 5 seconds/)).not.toBeInTheDocument();
    expect(screen.queryByLabelText("What should the owner know?")).not.toBeInTheDocument();
  });

  it("does nothing with the shortcuts switched off", async () => {
    window.localStorage.setItem("citedesk.shortcuts", "off");
    const user = setup();
    const { client } = detailClient();
    await open(client);
    await user.keyboard("a");
    expect(screen.queryByText(/Saved in 5 seconds/)).not.toBeInTheDocument();
  });

  it("goes from the queue to an approved reply with the keyboard alone", async () => {
    const user = setup();
    const { client, set } = detailClient();
    client.listInquiries = async () => ({
      items: [
        {
          id: 1,
          external_id: null,
          channel: "web_form",
          received_at: new Date().toISOString(),
          sender_name: "Priya S.",
          subject: "Kitchen drain, how much?",
          summary: "Asks how much a kitchen drain costs.",
          status: "needs_review",
          route: "draft_reply",
          urgency: "normal",
          primary_intent: "pricing_question",
          duplicate_of: null,
          is_synthetic: true,
        },
      ],
      next_cursor: null,
    });
    client.approve = vi.fn(async () => {
      set(approvedDetail());
      return approvedDetail();
    });
    client.exportText = async () => ({
      inquiry_id: 1,
      draft_id: 11,
      subject: "S",
      body: DRAFT_BODY,
    });
    client.recordExport = vi.fn(async () => ({
      inquiry_id: 1,
      draft_id: 11,
      subject: "S",
      body: DRAFT_BODY,
    }));
    const writeText = vi.fn(async () => {});
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText } });

    renderApp(client, "/");
    await screen.findByRole("link", { name: /Priya S\./ });
    await user.keyboard("j");
    await user.keyboard("{Enter}");
    await screen.findByRole("button", { name: "Approve reply" });
    await user.keyboard("a");
    await wait(5100);
    const copy = await screen.findByRole("button", { name: "Copy reply" });
    copy.focus();
    await user.keyboard("{Enter}");
    await waitFor(() => expect(writeText).toHaveBeenCalledWith(DRAFT_BODY));
    expect(client.recordExport).toHaveBeenCalledWith(11);
  });
});
