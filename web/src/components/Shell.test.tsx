import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { ApiError } from "../api/client";
import { expectAccessible } from "../test/axe";
import { fakeClient, renderApp, statusFixture } from "../test/render";
import { tabTitle } from "./Shell";

const DEMO = "Demo data. All customers and messages are invented.";

describe("the shell", () => {
  it("shows the demo-data notice before the status has loaded", () => {
    renderApp(fakeClient({ status: () => new Promise(() => {}) }));
    expect(screen.getByText(DEMO)).toBeInTheDocument();
  });

  it("keeps the notice when the status cannot be read", async () => {
    renderApp(
      fakeClient({
        status: async () => {
          throw new ApiError(0, "network", "Can't reach Citedesk.", null);
        },
      }),
    );
    await screen.findAllByText("Connection lost. Retrying.");
    expect(screen.getByText(DEMO)).toBeInTheDocument();
  });

  it("drops the notice only when the API says the data is real", async () => {
    renderApp(fakeClient({ status: async () => statusFixture({ synthetic_data: false }) }));
    await waitFor(() => expect(screen.queryByText(DEMO)).not.toBeInTheDocument());
  });

  it("names the urgent count and links to the filtered queue", async () => {
    const attention = { needs_review: 3, escalated: 1, failed: 0, urgent_open: 2 };
    renderApp(fakeClient({ status: async () => statusFixture({ attention }) }));
    const chip = await screen.findByRole("link", {
      name: "2 urgent inquiries waiting. Show them.",
    });
    expect(chip).toHaveTextContent("Urgent 2");
    expect(chip).toHaveAttribute("href", "/?urgency=urgent");
  });

  it("says plainly when nothing is urgent", async () => {
    renderApp(fakeClient());
    expect(await screen.findByText("No urgent items")).toBeInTheDocument();
  });

  it("puts what needs attention on the browser tab", async () => {
    const attention = { needs_review: 3, escalated: 1, failed: 1, urgent_open: 2 };
    renderApp(fakeClient({ status: async () => statusFixture({ attention }) }));
    await waitFor(() => expect(document.title).toBe("(2 urgent) Citedesk"));
  });

  it("builds the tab title from urgent, attention and section", () => {
    expect(tabTitle(2, 9, "/")).toBe("(2 urgent) Citedesk");
    expect(tabTitle(0, 5, "/")).toBe("(5) Citedesk");
    expect(tabTitle(0, 0, "/")).toBe("Citedesk");
    expect(tabTitle(0, 5, "/insights")).toBe("(5) Insights – Citedesk");
    expect(tabTitle(1, 1, "/settings")).toBe("(1 urgent) Settings – Citedesk");
  });

  it("announces a lost connection in the live region and in the bar", async () => {
    renderApp(
      fakeClient({
        status: async () => {
          throw new ApiError(0, "network", "Can't reach Citedesk.", null);
        },
      }),
    );
    const region = screen.getAllByRole("status")[0] as HTMLElement;
    await waitFor(() => expect(region).toHaveTextContent("Connection lost. Retrying."));
    expect(
      within(screen.getByRole("banner")).getByText("Connection lost. Retrying."),
    ).toBeVisible();
  });

  it("has a skip link as the first stop and a labelled main navigation", async () => {
    const user = userEvent.setup();
    renderApp(fakeClient());
    await user.tab();
    expect(screen.getByRole("link", { name: "Skip to the main content" })).toHaveFocus();
    const nav = screen.getByRole("navigation", { name: "Main" });
    expect(
      within(nav)
        .getAllByRole("link")
        .map((l) => l.textContent),
    ).toEqual(["Queue", "Insights", "Settings"]);
  });

  it("marks the current page and moves focus to the content after navigating", async () => {
    const user = userEvent.setup();
    renderApp(fakeClient());
    expect(screen.getByRole("link", { name: "Queue" })).toHaveAttribute("aria-current", "page");
    await user.click(screen.getByRole("link", { name: "Insights" }));
    expect(screen.getByRole("heading", { name: "Insights" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Insights" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("main")).toHaveFocus();
    expect(document.title).toBe("Insights – Citedesk");
  });

  it("does not take focus on the first load", () => {
    renderApp(fakeClient());
    expect(screen.getByRole("main")).not.toHaveFocus();
  });

  it("shows a page that does not exist as a page, with a way back", async () => {
    renderApp(fakeClient(), "/nowhere");
    expect(
      await screen.findByRole("heading", { name: "That page does not exist" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to the queue" })).toHaveAttribute("href", "/");
  });

  it("has no accessibility violations loaded, failing or not found", async () => {
    const loaded = renderApp(fakeClient());
    await screen.findByText("No urgent items");
    await expectAccessible(loaded.container);
    loaded.unmount();

    const failing = renderApp(
      fakeClient({
        status: async () => {
          throw new ApiError(0, "network", "Can't reach Citedesk.", null);
        },
      }),
      "/nowhere",
    );
    await screen.findAllByText("Connection lost. Retrying.");
    await expectAccessible(failing.container);
  });
});
