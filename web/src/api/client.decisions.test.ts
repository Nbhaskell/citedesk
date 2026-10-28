import { describe, expect, it, vi } from "vitest";
import { createHttpClient } from "./client";

function recorder() {
  const fetchFn = vi.fn(
    async () =>
      new Response("{}", { status: 200, headers: { "Content-Type": "application/json" } }),
  );
  const client = createHttpClient(fetchFn as unknown as typeof fetch);
  const last = () => {
    const [url, init] = fetchFn.mock.calls[fetchFn.mock.calls.length - 1] as unknown as [
      string,
      RequestInit,
    ];
    return { url, init, headers: init.headers as Record<string, string> };
  };
  return { client, last };
}

describe("ApiClient calls", () => {
  it.each([
    [
      "approve",
      (c: ReturnType<typeof recorder>["client"]) => c.approve(5, { review_seconds: 9 }),
      "/api/drafts/5/approve",
      { review_seconds: 9 },
    ],
    [
      "reject",
      (c: ReturnType<typeof recorder>["client"]) => c.reject(5, { reason: "No" }),
      "/api/drafts/5/reject",
      { reason: "No" },
    ],
    [
      "redraft",
      (c: ReturnType<typeof recorder>["client"]) => c.redraft(5, { guidance: "Shorter" }),
      "/api/drafts/5/redraft",
      { guidance: "Shorter" },
    ],
    [
      "escalate",
      (c: ReturnType<typeof recorder>["client"]) => c.escalate(7, { note: "Owner" }),
      "/api/inquiries/7/escalate",
      { note: "Owner" },
    ],
    [
      "resolve",
      (c: ReturnType<typeof recorder>["client"]) => c.resolve(7, {}),
      "/api/inquiries/7/resolve",
      {},
    ],
  ])("%s posts a JSON body to the right place", async (_name, call, url, body) => {
    const { client, last } = recorder();
    await call(client);
    expect(last().url).toBe(url);
    expect(last().init.method).toBe("POST");
    expect(last().headers["Content-Type"]).toBe("application/json");
    expect(JSON.parse(last().init.body as string)).toEqual(body);
  });

  it("asks for reprocess and a recorded copy without a body", async () => {
    const { client, last } = recorder();
    await client.reprocess(7);
    expect([last().url, last().init.method, last().init.body]).toEqual([
      "/api/inquiries/7/reprocess",
      "POST",
      undefined,
    ]);
    await client.recordExport(5);
    expect([last().url, last().init.method]).toEqual(["/api/drafts/5/export", "POST"]);
  });

  it("reads the inquiry, the approved text and the settings with GET", async () => {
    const { client, last } = recorder();
    await client.inquiry(7);
    expect([last().url, last().init.method]).toEqual(["/api/inquiries/7", "GET"]);
    await client.exportText(5);
    expect([last().url, last().init.method]).toEqual(["/api/drafts/5/export", "GET"]);
    await client.settings();
    expect([last().url, last().init.method]).toEqual(["/api/settings", "GET"]);
  });

  it("keeps a decision alive if the page is left, and not a read", async () => {
    const { client, last } = recorder();
    await client.approve(5, {});
    expect(last().init.keepalive).toBe(true);
    await client.inquiry(5);
    expect(last().init.keepalive).toBe(false);
  });

  it("has no call that sends a message to a customer", () => {
    const names = Object.keys(createHttpClient(fetch));
    expect(names.filter((n) => /send|mail/i.test(n))).toEqual([]);
  });
});
