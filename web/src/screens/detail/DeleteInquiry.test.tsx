import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../../api/client";
import type { InquiryStatus } from "../../api/types";
import { expectAccessible } from "../../test/axe";
import { detailClient, inState } from "../../test/detail";
import { detailFixture, renderApp } from "../../test/render";

const inStatus = (status: InquiryStatus) => {
  const base = detailFixture();
  return inState(status, { inquiry: { ...base.inquiry, status } });
};

const open = async (status: InquiryStatus = "needs_review") => {
  const { client } = detailClient(inStatus(status));
  const view = renderApp(client, "/inquiries/1");
  await screen.findByRole("heading", { name: /^Inquiry \d+/ });
  return { client, ...view };
};

describe("Detail: delete the inquiry (D-101)", () => {
  it("asks first, then deletes and goes back to the queue", async () => {
    const user = userEvent.setup();
    const { client, container } = await open();
    client.deleteInquiry = vi.fn(async () => undefined);
    await user.click(screen.getByRole("button", { name: "Delete inquiry…" }));
    expect(client.deleteInquiry).not.toHaveBeenCalled();
    expect(screen.getByText(/This cannot be undone\./)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Delete for good" })).toHaveFocus();
    await expectAccessible(container);
    await user.click(screen.getByRole("button", { name: "Delete for good" }));
    expect(client.deleteInquiry).toHaveBeenCalledWith(1);
    expect(await screen.findByRole("heading", { name: "Queue" })).toBeInTheDocument();
  });

  it("can be called off, and nothing is deleted", async () => {
    const user = userEvent.setup();
    const { client } = await open();
    client.deleteInquiry = vi.fn(async () => undefined);
    await user.click(screen.getByRole("button", { name: "Delete inquiry…" }));
    await user.click(screen.getByRole("button", { name: "Keep it" }));
    expect(client.deleteInquiry).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Delete inquiry…" })).toHaveFocus();
  });

  it("says when deleting did not work and stays on the page", async () => {
    const user = userEvent.setup();
    const { client } = await open("exported");
    client.deleteInquiry = vi.fn(async () => {
      throw new ApiError(409, "wrong_state", "This inquiry is still being processed.", "r1");
    });
    await user.click(screen.getByRole("button", { name: "Delete inquiry…" }));
    await user.click(screen.getByRole("button", { name: "Delete for good" }));
    // On the page and in the live region.
    expect(await screen.findAllByText(/still being processed/)).toHaveLength(2);
    expect(screen.getByRole("heading", { name: /^Inquiry 1/ })).toBeInTheDocument();
  });

  it("is not offered while the inquiry is being prepared", async () => {
    await open("screened");
    expect(screen.queryByRole("button", { name: "Delete inquiry…" })).not.toBeInTheDocument();
  });
});
