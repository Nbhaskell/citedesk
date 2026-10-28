import { vi } from "vitest";
import type { ApiClient } from "../api/client";
import type { InquiryDetail, InquiryStatus } from "../api/types";
import { detailFixture, fakeClient } from "./render";

/** The fixture in another status, later than the one it replaces so a decision's answer wins. */
export function inState(
  status: InquiryStatus,
  over: Partial<InquiryDetail> = {},
  at = "2026-10-28T12:05:00Z",
): InquiryDetail {
  const base = detailFixture();
  return {
    ...base,
    inquiry: { ...base.inquiry, status, updated_at: at },
    ...over,
  };
}

/**
 * A client for one inquiry that remembers what a decision changed, so what the screen refreshes
 * to agrees with what the decision answered. `calls` records what the screen asked.
 */
export function detailClient(
  start: InquiryDetail = detailFixture(),
  over: Partial<ApiClient> = {},
) {
  let current = start;
  const set = (next: InquiryDetail) => {
    current = next;
  };
  const inquiry = vi.fn(async () => current);
  const client = fakeClient({ inquiry, ...over });
  return { client, inquiry, set, get: () => current };
}

export function stubClipboard(writeText: (text: string) => Promise<void> = async () => {}) {
  const spy = vi.fn(writeText);
  Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: { writeText: spy },
  });
  return spy;
}
