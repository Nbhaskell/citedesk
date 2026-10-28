import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../api/client";
import { useResource } from "./useResource";

let visibility: DocumentVisibilityState = "visible";

beforeEach(() => {
  visibility = "visible";
  Object.defineProperty(document, "visibilityState", { configurable: true, get: () => visibility });
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

const flush = () => act(async () => vi.advanceTimersByTimeAsync(0));
const wait = (ms: number) => act(async () => vi.advanceTimersByTimeAsync(ms));

describe("useResource", () => {
  it("is loading, then has the data", async () => {
    const load = vi.fn(async () => "first");
    const { result } = renderHook(() => useResource(load));
    expect(result.current).toMatchObject({ data: null, loading: true, error: null });
    await flush();
    expect(result.current).toMatchObject({ data: "first", loading: false, error: null });
    await wait(60_000);
    expect(load).toHaveBeenCalledTimes(1);
  });

  it("refreshes on its interval, one request at a time", async () => {
    let calls = 0;
    const load = vi.fn(async () => ++calls);
    const { result } = renderHook(() => useResource(load, { intervalMs: 1000 }));
    await flush();
    expect(result.current.data).toBe(1);
    await wait(1000);
    expect(result.current.data).toBe(2);
    await wait(2000);
    expect(result.current.data).toBe(4);
  });

  it("does not start a request while the tab is hidden, and catches up when it is shown", async () => {
    let calls = 0;
    const load = vi.fn(async () => ++calls);
    renderHook(() => useResource(load, { intervalMs: 1000 }));
    await flush();
    visibility = "hidden";
    await wait(5000);
    expect(calls).toBe(1);
    visibility = "visible";
    await act(async () => {
      document.dispatchEvent(new Event("visibilitychange"));
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(calls).toBe(2);
  });

  it("keeps the last good data when a refresh fails, and clears the error on success", async () => {
    let fail = false;
    const load = vi.fn(async () => {
      if (fail) throw new ApiError(0, "network", "Can't reach Citedesk.", null);
      return "good";
    });
    const { result } = renderHook(() => useResource(load, { intervalMs: 1000 }));
    await flush();
    fail = true;
    await wait(1000);
    expect(result.current.data).toBe("good");
    expect(result.current.error).toMatchObject({ code: "network" });
    fail = false;
    await wait(1000);
    expect(result.current.error).toBeNull();
  });

  it("wraps a failure that is not an ApiError instead of crashing the screen", async () => {
    const load = vi.fn(async () => {
      throw new Error("boom with private text");
    });
    const { result } = renderHook(() => useResource(load));
    await flush();
    expect(result.current.error).toMatchObject({ code: "unexpected" });
    expect(result.current.error?.message).not.toContain("private");
  });

  it("loads again when told to, and when the key changes", async () => {
    const load = vi.fn(async () => "x");
    const { result, rerender } = renderHook(({ key }) => useResource(load, { key }), {
      initialProps: { key: "a" },
    });
    await flush();
    expect(load).toHaveBeenCalledTimes(1);
    act(() => result.current.reload());
    await flush();
    expect(load).toHaveBeenCalledTimes(2);
    rerender({ key: "b" });
    await flush();
    expect(load).toHaveBeenCalledTimes(3);
  });

  it("never shows the answer to another key: a new key is loading again", async () => {
    const load = vi.fn(async () => "x");
    let release: (value: string) => void = () => {};
    const { result, rerender } = renderHook(({ key }) => useResource(load, { key }), {
      initialProps: { key: "a" },
    });
    await flush();
    expect(result.current).toMatchObject({ data: "x", loading: false });
    load.mockImplementationOnce(() => new Promise<string>((resolve) => (release = resolve)));
    rerender({ key: "b" });
    expect(result.current).toMatchObject({ data: null, loading: true, error: null });
    await act(async () => release("y"));
    expect(result.current).toMatchObject({ data: "y", loading: false });
  });

  it("does not carry old data into a failure for a new key", async () => {
    const load = vi.fn(async () => "x");
    const { result, rerender } = renderHook(({ key }) => useResource(load, { key }), {
      initialProps: { key: "a" },
    });
    await flush();
    load.mockRejectedValueOnce(new ApiError(0, "network", "Can't reach Citedesk.", null));
    rerender({ key: "b" });
    await flush();
    expect(result.current).toMatchObject({ data: null, loading: false });
    expect(result.current.error).toMatchObject({ code: "network" });
  });

  it("aborts the request and stops polling when it unmounts", async () => {
    let signal: AbortSignal | undefined;
    const load = vi.fn(async (s: AbortSignal) => {
      signal = s;
      return "x";
    });
    const { unmount } = renderHook(() => useResource(load, { intervalMs: 1000 }));
    await flush();
    unmount();
    expect(signal?.aborted).toBe(true);
    await wait(10_000);
    expect(load).toHaveBeenCalledTimes(1);
  });
});
