import { act, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { modalOpen } from "../hooks/modal";
import { detailClient } from "../test/detail";
import { expectAccessible } from "../test/axe";
import { fakeClient, renderApp } from "../test/render";

beforeEach(() => vi.useFakeTimers({ shouldAdvanceTime: true }));
afterEach(() => {
  vi.useRealTimers();
  window.localStorage.clear();
});

const setup = () => userEvent.setup({ advanceTimers: (ms) => vi.advanceTimersByTime(ms) });
const dialog = () => screen.getByRole("dialog", { name: "Keyboard shortcuts" });

describe("the shortcut list", () => {
  it("opens with ? and lists the keys by where they work, with focus on Close", async () => {
    const user = setup();
    const { container } = renderApp(fakeClient());
    await screen.findByRole("heading", { name: "Queue" });
    await user.keyboard("?");

    const box = dialog();
    expect(box).toHaveAttribute("aria-modal", "true");
    for (const group of ["Anywhere", "In the queue", "On an inquiry"]) {
      expect(within(box).getByRole("heading", { name: group })).toBeInTheDocument();
    }
    expect(within(box).getByText("Approve the reply")).toBeInTheDocument();
    expect(within(box).getByText("Open the inquiry")).toBeInTheDocument();
    expect(box).toHaveFocus(); // not Close, which would scroll the title away on a short screen
    expect(modalOpen()).toBe(true);
    await expectAccessible(container);
  });

  it("opens from the button in the footer, which works with shortcuts switched off", async () => {
    window.localStorage.setItem("citedesk.shortcuts", "off");
    const user = setup();
    renderApp(fakeClient());
    await screen.findByRole("heading", { name: "Queue" });
    await user.keyboard("?");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Shortcuts" }));
    expect(
      within(dialog()).getByText(
        "Single-key shortcuts are switched off in this browser. Turn them on in Settings.",
      ),
    ).toBeInTheDocument();
  });

  it("says nothing about being switched off when they are on", async () => {
    const user = setup();
    renderApp(fakeClient());
    await user.click(await screen.findByRole("button", { name: "Shortcuts" }));
    expect(within(dialog()).queryByText(/switched off/)).not.toBeInTheDocument();
  });

  it("closes with Escape, with Close, with ?, and on a click outside, and gives focus back", async () => {
    const user = setup();
    renderApp(fakeClient());
    const opener = await screen.findByRole("button", { name: "Shortcuts" });

    await user.click(opener);
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(opener).toHaveFocus();
    expect(modalOpen()).toBe(false);

    await user.click(opener);
    await user.click(within(dialog()).getByRole("button", { name: "Close" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(opener).toHaveFocus();

    await user.click(opener);
    await user.keyboard("?");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    await user.click(opener);
    await user.click(screen.getByTestId("shortcut-backdrop"));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("keeps Tab inside the dialog", async () => {
    const user = setup();
    renderApp(fakeClient());
    await user.click(await screen.findByRole("button", { name: "Shortcuts" }));
    await user.tab();
    expect(within(dialog()).getByRole("button", { name: "Close" })).toHaveFocus();
    await user.tab({ shift: true });
    expect(within(dialog()).getByRole("button", { name: "Close" })).toHaveFocus();
  });

  it("is not opened by a ? typed into a box", async () => {
    const user = setup();
    renderApp(fakeClient());
    await user.type(await screen.findByLabelText("Search inquiries"), "why?");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("makes the page behind it ignore keys, and Escape closes it without also going back", async () => {
    const user = setup();
    const { client } = detailClient();
    renderApp(client, "/inquiries/1");
    await screen.findByRole("button", { name: "Approve reply" });

    await user.keyboard("?");
    await user.keyboard("a"); // would start an approval behind the dialog
    await act(async () => vi.advanceTimersByTimeAsync(100));
    expect(screen.queryByText(/Saved in 5 seconds/)).not.toBeInTheDocument();

    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Inquiry 1" })).toBeInTheDocument();

    // and with the dialog gone the keys work again
    await user.keyboard("a");
    expect(await screen.findByText(/Saved in 5 seconds/)).toBeInTheDocument();
  });
});
