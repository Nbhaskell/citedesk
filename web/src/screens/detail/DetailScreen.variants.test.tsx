import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../../api/client";
import type { AuditEvent, Escalation, InquiryDetail, InquiryStatus } from "../../api/types";
import { expectAccessible } from "../../test/axe";
import { detailClient, inState, stubClipboard } from "../../test/detail";
import { DRAFT_BODY, detailFixture, fakeClient, renderApp } from "../../test/render";

afterEach(() => vi.useRealTimers());

const LATER = "2026-10-28T12:05:00Z";

/** The fixture in another status, with some fields of the inquiry itself changed. */
function make(
  status: InquiryStatus,
  inquiry: Partial<InquiryDetail["inquiry"]> = {},
  over: Partial<InquiryDetail> = {},
): InquiryDetail {
  const base = detailFixture();
  return inState(status, {
    inquiry: { ...base.inquiry, status, updated_at: LATER, ...inquiry },
    ...over,
  });
}

const escalation = (over: Partial<Escalation> = {}): Escalation => ({
  id: 1,
  inquiry_id: 1,
  reason_code: "HEALTH_SAFETY",
  detail: "The message mentions an emergency",
  source: "rule",
  resolved: false,
  resolved_at: null,
  created_at: LATER,
  ...over,
});

const blockedChecks = () =>
  detailFixture().checks.map((c) =>
    c.check_code === "FIGURES_GROUNDED"
      ? { ...c, passed: false, detail: { ungrounded: ["$85"], derived: [], grounded: ["$149"] } }
      : c,
  );

const open = async (client: ReturnType<typeof fakeClient>, path = "/inquiries/1") => {
  const view = renderApp(client, path);
  await screen.findByRole("heading", { name: /^Inquiry \d+/ });
  return view;
};

describe("Detail: still being prepared", () => {
  const raw = () =>
    make(
      "screened",
      {},
      { classification: null, extraction: null, draft: null, checks: [], retrievals: [] },
    );

  it("says what is happening, offers no decision, and says the model has not read it yet", async () => {
    const { client } = detailClient(raw());
    const { container } = await open(client);
    expect(await screen.findByRole("heading", { name: "Being prepared" })).toBeInTheDocument();
    expect(screen.getByText("Reading the message…")).toBeInTheDocument();
    expect(screen.getByText("The model has not read this message.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Approve reply" })).not.toBeInTheDocument();
    expect(screen.queryByRole("region", { name: /Sources/ })).not.toBeInTheDocument();
    await expectAccessible(container);
  });

  it("names the stage by what has happened so far", async () => {
    const lookingUp = make("routed", {}, { draft: null, checks: [], retrievals: [] });
    await open(detailClient(lookingUp).client);
    expect(screen.getByText("Looking up your documents…")).toBeInTheDocument();
  });

  it("turns into the review screen by itself when the draft is ready", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const { client, set } = detailClient(raw());
    await open(client);
    expect(screen.queryByLabelText("Reply")).not.toBeInTheDocument();
    set(detailFixture());
    await act(async () => vi.advanceTimersByTimeAsync(3100));
    expect(await screen.findByRole("button", { name: "Approve reply" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Being prepared" })).not.toBeInTheDocument();
  });
});

describe("Detail: failed", () => {
  const failed = () =>
    make("failed", {
      failure_stage: "check",
      failure_message: "Checking crashed twice (RuntimeError)",
    });

  it("says where it stopped, and that nothing was sent", async () => {
    const { client } = detailClient(failed());
    const { container } = await open(client);
    expect(screen.getByRole("heading", { name: "This inquiry stopped" })).toBeInTheDocument();
    expect(screen.getByText("It failed while checking the draft.")).toBeInTheDocument();
    expect(screen.getByText("Checking crashed twice (RuntimeError)")).toBeInTheDocument();
    expect(screen.getByText(/Nothing was sent/)).toBeInTheDocument();
    await expectAccessible(container);
  });

  it("retries from the step that failed", async () => {
    const user = userEvent.setup();
    const { client, set } = detailClient(failed());
    const again = make("drafted");
    client.reprocess = vi.fn(async () => {
      set(again);
      return again;
    });
    await open(client);
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(client.reprocess).toHaveBeenCalledWith(1);
    expect(await screen.findByRole("heading", { name: "Being prepared" })).toBeInTheDocument();
  });
});

describe("Detail: escalated", () => {
  const escalated = () => make("escalated", {}, { escalations: [escalation()] });

  it("says why in plain words, keeps the draft folded away as reference, and offers no approval", async () => {
    const { client } = detailClient(escalated());
    const { container } = await open(client);
    expect(screen.getByRole("heading", { name: "This needs you" })).toBeInTheDocument();
    expect(
      screen.getAllByText("Mentions a gas smell, flooding or another safety risk").length,
    ).toBeGreaterThan(0);
    const reference = screen
      .getByText("For reference, not checked for sending")
      .closest("details")!;
    expect(reference).not.toHaveAttribute("open");
    expect(screen.queryByRole("button", { name: /Approve/ })).not.toBeInTheDocument();
    await expectAccessible(container);
  });

  it("is marked resolved, with a note if there is one", async () => {
    const user = userEvent.setup();
    const { client, set } = detailClient(escalated());
    const done = make("resolved");
    client.resolve = vi.fn(async () => {
      set(done);
      return done;
    });
    await open(client);
    await user.type(screen.getByLabelText("Note (optional)"), "Phoned the customer");
    await user.click(screen.getByRole("button", { name: "Mark resolved" }));
    expect(client.resolve).toHaveBeenCalledWith(1, { note: "Phoned the customer" });
    expect(await screen.findByText("This inquiry was marked resolved.")).toBeInTheDocument();
  });

  it("can be resolved without a note", async () => {
    const user = userEvent.setup();
    const { client } = detailClient(escalated());
    client.resolve = vi.fn(async () => make("resolved"));
    await open(client);
    await user.click(screen.getByRole("button", { name: "Mark resolved" }));
    expect(client.resolve).toHaveBeenCalledWith(1, {});
  });

  it("says when resolving did not work and keeps the note", async () => {
    const user = userEvent.setup();
    const { client } = detailClient(escalated());
    client.resolve = vi.fn(async () => {
      throw new ApiError(0, "network", "Can't reach Citedesk.", null);
    });
    await open(client);
    await user.type(screen.getByLabelText("Note (optional)"), "Keep me");
    await user.click(screen.getByRole("button", { name: "Mark resolved" }));
    expect(
      await screen.findByText("Can't reach Citedesk. Check that it is running on port 8100."),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Note (optional)")).toHaveValue("Keep me");
  });

  it("words a reason that came from a draft check differently", async () => {
    const detail = make(
      "escalated",
      {},
      {
        escalations: [escalation({ reason_code: "POLICY_EXCEPTION_REQUEST", source: "check" })],
      },
    );
    await open(detailClient(detail).client);
    expect(
      screen.getAllByText("The draft makes a promise only you can make").length,
    ).toBeGreaterThan(0);
  });
});

describe("Detail: a draft that failed a check", () => {
  const blocked = () => {
    const base = detailFixture();
    return make(
      "escalated",
      {},
      {
        draft: {
          ...base.draft!,
          status: "blocked",
          body: "Hi,\n\nThe price is $85.\n\nKind regards,\nK",
        },
        checks: blockedChecks(),
        escalations: [
          escalation({
            reason_code: "UNVERIFIED_FIGURE",
            source: "check",
            detail: "1 figure(s) in the draft are not in the sources",
          }),
        ],
      },
    );
  };

  it("says what is wrong, marks it in the draft, and cannot be approved", async () => {
    const { client } = detailClient(blocked());
    const { container } = await open(client);
    expect(screen.getByRole("heading", { name: "Not ready to send" })).toBeInTheDocument();
    expect(screen.getByText("Not ready: $85 isn't in your documents.")).toBeInTheDocument();
    const draft = screen.getByRole("region", { name: "Draft reply" });
    expect(draft.querySelector("mark")?.textContent).toBe("$85");
    expect(screen.queryByRole("button", { name: /Approve/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("textbox", { name: "Reply" })).not.toBeInTheDocument();
    const checks = screen.getByRole("region", { name: "Checks" });
    expect(within(checks).getByText("Needs attention")).toBeInTheDocument();
    expect(within(checks).getByText("Not in your documents: $85")).toBeInTheDocument();
    await expectAccessible(container);
  });

  it("puts the failed check before the ones that passed", async () => {
    await open(detailClient(blocked()).client);
    const checks = screen.getByRole("region", { name: "Checks" });
    const first = within(checks).getAllByRole("listitem")[0]!;
    expect(first).toHaveTextContent("Prices and dates match your documents");
    expect(first).toHaveTextContent("Needs attention");
  });
});

describe("Detail: the documents do not cover the question", () => {
  const refusal = () => {
    const base = detailFixture();
    return make(
      "escalated",
      {},
      {
        draft: {
          ...base.draft!,
          kind: "holding_reply",
          status: "blocked",
          body: "Hello,\n\nA member of our team will reply to you directly.\n\nKind regards,\nK",
          claims: [],
        },
        checks: [],
        retrievals: [],
        escalations: [escalation({ reason_code: "NOT_IN_KNOWLEDGE_BASE", detail: null })],
      },
    );
  };

  it("says so, does not pretend there are sources, and keeps the holding reply for reference", async () => {
    const { client } = detailClient(refusal());
    const { container } = await open(client);
    expect(
      screen.getByRole("heading", { name: "The documents don't cover this question" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/will not answer from memory/)).toBeInTheDocument();
    expect(screen.getByText("No passages were used.")).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Checks" })).not.toBeInTheDocument();
    expect(screen.getByText(/A holding reply was written/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Mark resolved" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Approve/ })).not.toBeInTheDocument();
    await expectAccessible(container);
  });
});

describe("Detail: a rejected draft", () => {
  const rejected = () => {
    const base = detailFixture();
    return make("rejected", {}, { draft: { ...base.draft!, status: "rejected" } });
  };

  it("asks what to change before writing a new draft", async () => {
    const user = userEvent.setup();
    const { client } = detailClient(rejected());
    client.redraft = vi.fn();
    const { container } = await open(client);
    await expectAccessible(container);
    await user.click(screen.getByRole("button", { name: "Write a new draft" }));
    expect(screen.getByText("Say what to change.")).toBeInTheDocument();
    expect(client.redraft).not.toHaveBeenCalled();
  });

  it("says it is writing, then shows the new draft for review", async () => {
    const user = userEvent.setup();
    const { client, set } = detailClient(rejected());
    let finish: (detail: InquiryDetail) => void = () => {};
    client.redraft = vi.fn(() => new Promise<InquiryDetail>((resolve) => (finish = resolve)));
    await open(client);
    await user.type(screen.getByLabelText("What should the new draft do differently?"), "Shorter");
    await user.click(screen.getByRole("button", { name: "Write a new draft" }));
    expect(client.redraft).toHaveBeenCalledWith(11, { guidance: "Shorter" });
    expect(
      await screen.findByText("Writing a new draft. This can take up to a minute."),
    ).toBeInTheDocument();
    const next = make(
      "needs_review",
      {},
      {
        draft: { ...detailFixture().draft!, id: 12, version: 2, guidance: "Shorter" },
      },
    );
    set(next);
    await act(async () => finish(next));
    expect(await screen.findByRole("button", { name: "Approve reply" })).toBeInTheDocument();
  });

  it("says when the model gave no usable draft and keeps the guidance", async () => {
    const user = userEvent.setup();
    const { client } = detailClient(rejected());
    client.redraft = vi.fn(async () => {
      throw new ApiError(
        502,
        "model_failed",
        "The model gave no usable reply. Nothing was changed; try again.",
        "req5",
      );
    });
    await open(client);
    await user.type(
      screen.getByLabelText("What should the new draft do differently?"),
      "Friendlier",
    );
    await user.click(screen.getByRole("button", { name: "Write a new draft" }));
    const main = screen.getByRole("main");
    await waitFor(() =>
      expect(
        within(main).getByText(/The model gave no usable reply\. Nothing was changed; try again\./),
      ).toBeInTheDocument(),
    );
    expect(screen.getByLabelText("What should the new draft do differently?")).toHaveValue(
      "Friendlier",
    );
  });

  it("can be closed without a reply", async () => {
    const user = userEvent.setup();
    const { client } = detailClient(rejected());
    client.resolve = vi.fn(async () => make("resolved"));
    await open(client);
    await user.click(screen.getByRole("button", { name: "Close without a reply" }));
    expect(client.resolve).toHaveBeenCalledWith(1, {});
  });
});

describe("Detail: approved", () => {
  const approved = () =>
    make("approved", {}, { draft: { ...detailFixture().draft!, status: "approved" } });
  const text = {
    inquiry_id: 1,
    draft_id: 11,
    subject: "Re: Kitchen drain, how much?",
    body: DRAFT_BODY,
  };

  it("shows the approved text and says nothing is sent", async () => {
    const { client } = detailClient(approved());
    client.exportText = async () => text;
    const { container } = await open(client);
    expect(screen.getByRole("heading", { name: "Reply approved" })).toBeInTheDocument();
    expect(
      await screen.findByText(/Drain cleaning for one fixture starts at \$149/),
    ).toBeInTheDocument();
    expect(screen.getAllByText(/Nothing is sent from Citedesk/).length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: /send/i })).not.toBeInTheDocument();
    await expectAccessible(container);
  });

  it("copies the reply, records the copy and shows that it was copied", async () => {
    const user = userEvent.setup();
    const { client, set } = detailClient(approved());
    const writeText = stubClipboard();
    const copied = make(
      "exported",
      {},
      { draft: { ...detailFixture().draft!, status: "approved" } },
    );
    client.exportText = async () => text;
    client.recordExport = vi.fn(async () => {
      set(copied);
      return text;
    });
    await open(client);
    await user.click(await screen.findByRole("button", { name: "Copy reply" }));
    expect(writeText).toHaveBeenCalledWith(DRAFT_BODY);
    expect(client.recordExport).toHaveBeenCalledWith(11);
    expect(await screen.findByRole("heading", { name: "Copied" })).toBeInTheDocument();
    expect(
      screen.getByText("The reply was copied. Nothing was sent from Citedesk."),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Copy again" })).toBeInTheDocument();
    await waitFor(() =>
      expect(
        screen.getAllByRole("status").some((r) => r.textContent === "Copied. Nothing was sent."),
      ).toBe(true),
    );
  });

  it("does not record a copy that did not happen", async () => {
    const user = userEvent.setup();
    const { client } = detailClient(approved());
    stubClipboard(async () => {
      throw new Error("denied");
    });
    client.exportText = async () => text;
    client.recordExport = vi.fn();
    await open(client);
    await user.click(await screen.findByRole("button", { name: "Copy reply" }));
    expect(
      await screen.findByText("Couldn't copy. Select the text above and copy it yourself."),
    ).toBeInTheDocument();
    expect(client.recordExport).not.toHaveBeenCalled();
  });
});

describe("Detail: closed", () => {
  it.each([
    ["resolved", "This inquiry was marked resolved."],
    ["archived", "This inquiry was archived."],
  ] as const)("%s says so and offers the way back", async (status, sentence) => {
    const { client } = detailClient(make(status));
    const { container } = await open(client);
    expect(screen.getByText(sentence)).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /Approve|Reject|Escalate/ }),
    ).not.toBeInTheDocument();
    await expectAccessible(container);
  });
});

describe("Detail: history", () => {
  it("lists what happened in plain words, folded away", async () => {
    const event = (id: number, over: Partial<AuditEvent>): AuditEvent => ({
      id,
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
    const detail = {
      ...detailFixture(),
      history: [
        event(1, {
          event_type: "stage_finished",
          stage: "check",
          payload: { blocking_failed: [], warnings_failed: [] },
        }),
        event(2, { event_type: "review_recorded", payload: { decision: "edit_approve" } }),
      ],
    };
    await open(detailClient(detail).client);
    const summary = screen.getByText("History (2)");
    expect(summary.closest("details")).not.toHaveAttribute("open");
    expect(screen.getByText("Checked: all passed", { exact: false })).toBeInTheDocument();
    expect(
      screen.getByText("Edited and approved by a reviewer", { exact: false }),
    ).toBeInTheDocument();
  });
});

describe("Detail: loading, errors and bad addresses", () => {
  it("says it is loading and shows placeholders", async () => {
    const client = fakeClient({ inquiry: () => new Promise(() => {}) });
    const { container } = renderApp(client, "/inquiries/1");
    expect(screen.getByText("Loading the inquiry")).toBeInTheDocument();
    expect(container.querySelector("[aria-busy='true']")).not.toBeNull();
    await expectAccessible(container);
  });

  it("says it cannot reach Citedesk and retries on request", async () => {
    const user = userEvent.setup();
    let fail = true;
    const client = fakeClient({
      inquiry: async () => {
        if (fail) throw new ApiError(0, "network", "Can't reach Citedesk.", null);
        return detailFixture();
      },
    });
    const { container } = renderApp(client, "/inquiries/1");
    expect(
      await screen.findByText("Can't reach Citedesk. Check that it is running on port 8100."),
    ).toBeInTheDocument();
    await expectAccessible(container);
    fail = false;
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByRole("button", { name: "Approve reply" })).toBeInTheDocument();
  });

  it("says no inquiry has that number, with a way back", async () => {
    const client = fakeClient({
      inquiry: async () => {
        throw new ApiError(404, "not_found", "No inquiry has that id.", "r1");
      },
    });
    renderApp(client, "/inquiries/99");
    expect(await screen.findByText("No inquiry has that number.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to the queue" })).toHaveAttribute("href", "/");
  });

  it("treats an address that is not a number the same way, without asking the server", async () => {
    const inquiry = vi.fn();
    renderApp(fakeClient({ inquiry }), "/inquiries/abc");
    expect(await screen.findByText("No inquiry has that number.")).toBeInTheDocument();
  });
});
