import { describe, expect, it, vi } from "vitest";
import { ApiError, createHttpClient } from "./client";

function reply(body: unknown, init: ResponseInit = {}): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json", "X-Request-ID": "req123", ...init.headers },
    ...init,
  });
}

describe("createHttpClient", () => {
  it("reads the status from the API's own origin", async () => {
    const fetchFn = vi.fn(async () => reply({ status: "ok" }));
    const client = createHttpClient(fetchFn as unknown as typeof fetch);
    await expect(client.status()).resolves.toEqual({ status: "ok" });
    const [url, init] = fetchFn.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/api/status");
    expect(init.method).toBe("GET");
  });

  it("asks for a service check with POST and no body", async () => {
    const fetchFn = vi.fn(async () => reply({ status: "ok" }));
    await createHttpClient(fetchFn as unknown as typeof fetch).checkStatus();
    const [url, init] = fetchFn.mock.calls[0] as unknown as [string, RequestInit];
    expect([url, init.method, init.body]).toEqual(["/api/status/check", "POST", undefined]);
  });

  it("turns the API's error shape into an ApiError with the request number", async () => {
    const body = {
      error: { code: "not_found", message: "No inquiry has that id.", request_id: "req123" },
    };
    const client = createHttpClient((async () => reply(body, { status: 404 })) as typeof fetch);
    const error = await client.status().catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      httpStatus: 404,
      code: "not_found",
      message: "No inquiry has that id.",
      requestId: "req123",
      unreachable: false,
    });
  });

  it("does not repeat an unexpected error body", async () => {
    const secret = "the customer's private message";
    const client = createHttpClient(
      (async () => new Response(`<html>${secret}</html>`, { status: 502 })) as typeof fetch,
    );
    const error = (await client.status().catch((e: unknown) => e)) as ApiError;
    expect(error.code).toBe("http_502");
    expect(error.message).not.toContain(secret);
  });

  it("reports an unreachable server as such", async () => {
    const client = createHttpClient((async () => {
      throw new TypeError("Failed to fetch");
    }) as typeof fetch);
    const error = (await client.status().catch((e: unknown) => e)) as ApiError;
    expect(error).toMatchObject({ httpStatus: 0, code: "network", unreachable: true });
  });

  it("lets an aborted request stay an abort, not an error to show", async () => {
    const controller = new AbortController();
    const client = createHttpClient((async (_url: string, init?: RequestInit) => {
      controller.abort();
      init?.signal?.throwIfAborted();
      return reply({});
    }) as unknown as typeof fetch);
    const error = await client.status(controller.signal).catch((e: unknown) => e);
    expect(error).not.toBeInstanceOf(ApiError);
    expect((error as DOMException).name).toBe("AbortError");
  });
});
