import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "../api/client";

export interface Resource<T> {
  /** The last good answer for the current key. It stays when a later refresh fails (see `error`). */
  data: T | null;
  /** The latest failure, cleared by the next success. */
  error: ApiError | null;
  /** True until the first answer or failure for the current key. */
  loading: boolean;
  /** Fetch again now. */
  reload: () => void;
}

interface Options {
  /** Refresh this often while the tab is visible. Omit to load once. */
  intervalMs?: number;
  /** Change this to load something else (a filter, an id). Data for another key is never shown. */
  key?: string;
}

interface Outcome<T> {
  key: string;
  data: T | null;
  error: ApiError | null;
}

function asApiError(error: unknown): ApiError {
  return error instanceof ApiError
    ? error
    : new ApiError(0, "unexpected", "Something went wrong in the page.", null);
}

/**
 * Load something and optionally keep it fresh. One request at a time (the next is scheduled when
 * the last finishes), paused while the tab is hidden and refreshed when it comes back. A failed
 * refresh keeps the old data and sets `error`, so the screen can say "connection lost" without
 * emptying itself. A new `key` starts again from loading: the answer to a different question is
 * never shown as if it answered this one.
 */
export function useResource<T>(
  load: (signal: AbortSignal) => Promise<T>,
  { intervalMs, key = "" }: Options = {},
): Resource<T> {
  const [outcome, setOutcome] = useState<Outcome<T> | null>(null);
  const [tick, setTick] = useState(0);
  const loadRef = useRef(load);

  useEffect(() => {
    loadRef.current = load;
  });

  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    let running = false;

    const run = async () => {
      if (running || controller.signal.aborted) return;
      running = true;
      try {
        const next = await loadRef.current(controller.signal);
        if (controller.signal.aborted) return;
        setOutcome({ key, data: next, error: null });
      } catch (caught) {
        if (controller.signal.aborted) return;
        const error = asApiError(caught);
        setOutcome((previous) => ({
          key,
          data: previous?.key === key ? previous.data : null,
          error,
        }));
      } finally {
        running = false;
        if (!controller.signal.aborted && intervalMs) timer = setTimeout(schedule, intervalMs);
      }
    };

    const schedule = () => {
      if (document.visibilityState === "visible") void run();
      else timer = setTimeout(schedule, intervalMs ?? 1000);
    };

    const onVisible = () => {
      if (document.visibilityState === "visible" && intervalMs) {
        clearTimeout(timer);
        void run();
      }
    };

    void run();
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      controller.abort();
      clearTimeout(timer);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [intervalMs, key, tick]);

  const reload = useCallback(() => setTick((n) => n + 1), []);
  const current = outcome?.key === key ? outcome : null;
  return {
    data: current?.data ?? null,
    error: current?.error ?? null,
    loading: current === null,
    reload,
  };
}
