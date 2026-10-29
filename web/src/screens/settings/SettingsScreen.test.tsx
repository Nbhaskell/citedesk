import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../../api/client";
import type { SettingsView, StatusResponse } from "../../api/types";
import { shortcutsEnabled } from "../../hooks/shortcuts";
import { expectAccessible } from "../../test/axe";
import { fakeClient, renderApp, settingsFixture, statusFixture } from "../../test/render";

const minutesAgo = (n: number) => new Date(Date.now() - n * 60_000).toISOString();

function withComponents(
  model: StatusResponse["components"]["model"],
  knowledgeBase: StatusResponse["components"]["knowledge_base"],
  over: Partial<StatusResponse> = {},
): StatusResponse {
  const base = statusFixture();
  return {
    ...base,
    components: { ...base.components, model, knowledge_base: knowledgeBase },
    ...over,
  };
}

function settingsClient(
  settings: () => Promise<SettingsView> = async () => settingsFixture(),
  status: () => Promise<StatusResponse> = async () => statusFixture(),
  over: Parameters<typeof fakeClient>[0] = {},
) {
  const settingsCall = vi.fn(settings);
  return { client: fakeClient({ settings: settingsCall, status, ...over }), settingsCall };
}

const service = (name: string) => {
  const item = screen.getByText(name).closest("li");
  if (!item) throw new Error(`no service called ${name}`);
  return within(item);
};

beforeEach(() => window.localStorage.clear());
afterEach(() => window.localStorage.clear());

describe("Settings: loading", () => {
  it("says it is loading and shows no settings", async () => {
    const { client } = settingsClient(() => new Promise(() => {}));
    const { container } = renderApp(client, "/settings");
    expect(screen.getByRole("heading", { name: "Settings" })).toBeInTheDocument();
    expect(screen.getByText("Loading the settings")).toBeInTheDocument();
    expect(container.querySelector("[aria-busy='true']")).not.toBeNull();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    await expectAccessible(container);
  });
});

describe("Settings: error", () => {
  it("says it cannot reach Citedesk and tries again on request", async () => {
    let fail = true;
    const { client, settingsCall } = settingsClient(async () => {
      if (fail) throw new ApiError(0, "network", "Can't reach Citedesk.", null);
      return settingsFixture();
    });
    const { container } = renderApp(client, "/settings");
    expect(
      await screen.findByText("Can't reach Citedesk. Check that it is running on port 8100."),
    ).toBeInTheDocument();
    await expectAccessible(container);
    fail = false;
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText("Kestrel Hollow Plumbing")).toBeInTheDocument();
    expect(settingsCall.mock.calls.length).toBeGreaterThanOrEqual(2);
  });
});

describe("Settings: what is in force", () => {
  it("shows the business, the reply limits and the data mode", async () => {
    const { client } = settingsClient();
    const { container } = renderApp(client, "/settings");
    expect(await screen.findByText("Kestrel Hollow Plumbing")).toBeInTheDocument();
    expect(screen.getByText("555-0171")).toBeInTheDocument();
    expect(screen.getByText("555-0172")).toBeInTheDocument();
    expect(screen.getByText("kestrelhollow@example.com")).toBeInTheDocument();
    expect(
      screen.getByText(
        "A reply must stay under 200 words, open with a greeting and end with a sign-off. This is checked in code.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Citedesk never sends anything. You copy an approved reply into your own email.",
      ),
    ).toBeInTheDocument();
    // the footer says it too, so look inside the Data section
    const data = screen.getByRole("heading", { name: "Data" }).closest("section");
    expect(
      within(data as HTMLElement).getByText("Demo data. All customers and messages are invented."),
    ).toBeInTheDocument();
    await expectAccessible(container);
  });

  it("says plainly when the data is real", async () => {
    const { client } = settingsClient(async () => settingsFixture({ synthetic_data: false }));
    renderApp(client, "/settings");
    expect(
      await screen.findByText("Real data. These are real customers' messages."),
    ).toBeInTheDocument();
  });

  it("says so when the business details could not be read", async () => {
    const { client } = settingsClient(async () => settingsFixture({ business: null }));
    renderApp(client, "/settings");
    expect(
      await screen.findByText(
        "The business details could not be read, so replies cannot name the business.",
      ),
    ).toBeInTheDocument();
  });

  it("lists every escalation rule in plain words and who sets it", async () => {
    const { client } = settingsClient();
    renderApp(client, "/settings");
    await screen.findByText("Kestrel Hollow Plumbing");
    const rows = within(
      screen.getByRole("table", { name: "When Citedesk escalates to you" }),
    ).getAllByRole("row");
    expect(rows).toHaveLength(11); // header and the ten reasons
    const gas = rows.find((row) => within(row).queryByText(/gas smell/));
    expect(gas).toHaveTextContent("On");
    expect(gas).toHaveTextContent("Fixed in code");
    const lowConfidence = rows.find((row) =>
      within(row).queryByText("Not sure what the customer wants"),
    );
    expect(lowConfidence).toHaveTextContent("The server's settings");
    expect(screen.getByText(/These rules can't be changed on this screen/)).toBeInTheDocument();
  });

  it("shows a rule that is switched off as Off, in words and not by colour alone", async () => {
    const base = settingsFixture();
    const { client } = settingsClient(async () => ({
      ...base,
      rules: base.rules.map((rule) =>
        rule.code === "LOW_CONFIDENCE" ? { ...rule, enabled: false } : rule,
      ),
    }));
    renderApp(client, "/settings");
    await screen.findByText("Kestrel Hollow Plumbing");
    const row = screen.getByText("Not sure what the customer wants").closest("tr");
    expect(row).toHaveTextContent("Off");
  });

  it("has no control that changes a rule or the business", async () => {
    const { client } = settingsClient();
    renderApp(client, "/settings");
    await screen.findByText("Kestrel Hollow Plumbing");
    const main = screen.getByRole("main");
    // the keyboard shortcuts switch is the only setting; the rest is read-only
    expect(within(main).getAllByRole("checkbox")).toHaveLength(1);
    expect(within(main).queryByRole("textbox")).not.toBeInTheDocument();
    expect(within(main).queryByRole("combobox")).not.toBeInTheDocument();
  });
});

describe("Settings: services", () => {
  it("says not checked yet, rather than showing a tick nobody earned", async () => {
    const { client } = settingsClient();
    renderApp(client, "/settings");
    await screen.findByText("Kestrel Hollow Plumbing");
    const model = service("Language model (qwen3:8b)");
    expect(model.getByText("Not checked yet")).toBeInTheDocument();
    expect(model.getByText("Citedesk has not asked the model server yet.")).toBeInTheDocument();
    expect(model.queryByText("Working")).not.toBeInTheDocument();
    expect(service("Documents service").getByText("Not checked yet")).toBeInTheDocument();
    // the database and the worker are known from every status poll
    expect(service("Database").getByText("Working")).toBeInTheDocument();
    expect(service("Background worker").getByText("Running")).toBeInTheDocument();
  });

  it("shows a working service with when it was checked", async () => {
    const { client } = settingsClient(
      async () => settingsFixture(),
      async () =>
        withComponents(
          { status: "ok", reason: null },
          { status: "ok", reason: null },
          { checked_at: minutesAgo(3) },
        ),
    );
    const { container } = renderApp(client, "/settings");
    await screen.findByText("Kestrel Hollow Plumbing");
    expect(await screen.findByText("Last checked 3 min ago.")).toBeInTheDocument();
    expect(service("Language model (qwen3:8b)").getByText("Working")).toBeInTheDocument();
    expect(service("Documents service").getByText("Working")).toBeInTheDocument();
    await expectAccessible(container);
  });

  it("says what is wrong in words, for the model and for the documents", async () => {
    const { client } = settingsClient(
      async () => settingsFixture(),
      async () =>
        withComponents(
          { status: "error", reason: "model_missing" },
          { status: "error", reason: "not_indexed" },
          { status: "degraded", checked_at: minutesAgo(1) },
        ),
    );
    const { container } = renderApp(client, "/settings");
    await screen.findByText("Kestrel Hollow Plumbing");
    await screen.findAllByText("Not working");
    expect(
      service("Language model (qwen3:8b)").getByText(
        "The model is not installed on the model server.",
      ),
    ).toBeInTheDocument();
    expect(
      service("Documents service").getByText("The documents have not been indexed yet."),
    ).toBeInTheDocument();
    await expectAccessible(container);
  });

  it("falls back to a plain sentence for a reason it has no words for", async () => {
    const { client } = settingsClient(
      async () => settingsFixture(),
      async () =>
        withComponents(
          { status: "error", reason: "something_new" },
          { status: "ok", reason: null },
        ),
    );
    renderApp(client, "/settings");
    await screen.findByText("Kestrel Hollow Plumbing");
    await screen.findByText("Not working");
    expect(
      service("Language model (qwen3:8b)").getByText("No reason was given."),
    ).toBeInTheDocument();
  });

  it("asks again on request, shows that it is checking, then the new answer", async () => {
    let finish: (value: StatusResponse) => void = () => {};
    const checkStatus = vi.fn(() => new Promise<StatusResponse>((resolve) => (finish = resolve)));
    const { client } = settingsClient(undefined, undefined, { checkStatus });
    renderApp(client, "/settings");
    await screen.findByText("Kestrel Hollow Plumbing");
    await userEvent.click(screen.getByRole("button", { name: "Check again" }));
    expect(checkStatus).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: "Checking…" })).toBeDisabled();
    finish(
      withComponents(
        { status: "ok", reason: null },
        { status: "error", reason: "unreachable" },
        { checked_at: new Date().toISOString() },
      ),
    );
    expect(await screen.findByRole("button", { name: "Check again" })).toBeEnabled();
    expect(service("Language model (qwen3:8b)").getByText("Working")).toBeInTheDocument();
    const documents = service("Documents service");
    expect(documents.getByText("Not working")).toBeInTheDocument();
    expect(documents.getByText("Citedesk could not reach it.")).toBeInTheDocument();
    expect(screen.getByText("Last checked just now.")).toBeInTheDocument();
  });

  it("says when the check itself could not run, and keeps what it knew", async () => {
    const checkStatus = vi.fn(async () => {
      throw new ApiError(0, "network", "Can't reach Citedesk.", null);
    });
    const { client } = settingsClient(
      async () => settingsFixture(),
      async () =>
        withComponents(
          { status: "ok", reason: null },
          { status: "ok", reason: null },
          { checked_at: minutesAgo(10) },
        ),
      { checkStatus },
    );
    renderApp(client, "/settings");
    await screen.findByText("Kestrel Hollow Plumbing");
    await screen.findByText("Last checked 10 min ago.");
    await userEvent.click(screen.getByRole("button", { name: "Check again" }));
    // the page has its own empty alert region for announcements, so find this one by its words
    const alert = await screen.findByText(/Couldn't run the check\./);
    expect(alert).toHaveAttribute("role", "alert");
    expect(alert).toHaveTextContent("Can't reach Citedesk. Check that it is running on port 8100.");
    expect(screen.getByText("Last checked 10 min ago.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Check again" })).toBeEnabled();
  });

  it("says the status may be out of date when the connection is lost", async () => {
    const { client } = settingsClient(
      async () => settingsFixture(),
      async () => {
        throw new ApiError(0, "network", "Can't reach Citedesk.", null);
      },
    );
    renderApp(client, "/settings");
    await screen.findByText("Kestrel Hollow Plumbing");
    expect(await screen.findByText(/may be out of date/)).toBeInTheDocument();
    expect(service("Language model (qwen3:8b)").getByText("Not checked yet")).toBeInTheDocument();
  });

  it("reports a stopped worker", async () => {
    const { client } = settingsClient(
      async () => settingsFixture(),
      async () => statusFixture({ worker_running: false }),
    );
    renderApp(client, "/settings");
    await screen.findByText("Kestrel Hollow Plumbing");
    expect(await service("Background worker").findByText("Stopped")).toBeInTheDocument();
  });
});

describe("Settings: this browser", () => {
  it("starts with shortcuts on and switches them off for good", async () => {
    const { client } = settingsClient();
    renderApp(client, "/settings");
    const box = await screen.findByRole("checkbox", { name: "Use keyboard shortcuts" });
    expect(box).toBeChecked();
    await userEvent.click(box);
    expect(box).not.toBeChecked();
    expect(shortcutsEnabled()).toBe(false);
    expect(window.localStorage.getItem("citedesk.shortcuts")).toBe("off");
    await userEvent.click(box);
    expect(shortcutsEnabled()).toBe(true);
  });

  it("shows the saved choice on the next visit", async () => {
    window.localStorage.setItem("citedesk.shortcuts", "off");
    renderApp(settingsClient().client, "/settings");
    expect(
      await screen.findByRole("checkbox", { name: "Use keyboard shortcuts" }),
    ).not.toBeChecked();
  });

  it("says so when the browser will not keep the choice", async () => {
    const setItem = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    try {
      renderApp(settingsClient().client, "/settings");
      await userEvent.click(
        await screen.findByRole("checkbox", { name: "Use keyboard shortcuts" }),
      );
      expect(
        screen.getByText(
          "Couldn't keep this choice in this browser. It will reset when the page reloads.",
        ),
      ).toBeInTheDocument();
    } finally {
      setItem.mockRestore();
    }
  });
});
