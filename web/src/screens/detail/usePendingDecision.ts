import { useCallback, useEffect, useRef, useState } from "react";

export const UNDO_MS = 5000;

interface Job {
  label: string;
  run: () => Promise<boolean>;
}

/**
 * A decision that waits a few seconds, visibly, so it can be undone (docs/UI_DESIGN_PLAN.md
 * section 1, decision 1). The API has no undo, so the request is simply not sent until the time
 * is up. It is sent at once if the person leaves the page, hides the tab or closes it, so a
 * decision is never lost by leaving. `run` answers whether it was saved.
 */
export function usePendingDecision(delayMs: number = UNDO_MS) {
  const [secondsLeft, setSecondsLeft] = useState<number | null>(null);
  const [label, setLabel] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const job = useRef<Job | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const ticker = useRef<ReturnType<typeof setInterval> | undefined>(undefined);

  const stopTimers = useCallback(() => {
    clearTimeout(timer.current);
    clearInterval(ticker.current);
  }, []);

  const send = useCallback(async () => {
    const current = job.current;
    if (!current) return;
    job.current = null;
    stopTimers();
    setSecondsLeft(null);
    setSaving(true);
    try {
      await current.run();
    } finally {
      setSaving(false);
      setLabel(null);
    }
  }, [stopTimers]);

  const start = useCallback(
    (nextLabel: string, run: () => Promise<boolean>) => {
      if (job.current) return;
      job.current = { label: nextLabel, run };
      setLabel(nextLabel);
      setSecondsLeft(Math.ceil(delayMs / 1000));
      timer.current = setTimeout(() => void send(), delayMs);
      ticker.current = setInterval(
        () => setSecondsLeft((n) => (n === null ? null : Math.max(1, n - 1))),
        1000,
      );
    },
    [delayMs, send],
  );

  const undo = useCallback(() => {
    if (!job.current) return;
    job.current = null;
    stopTimers();
    setSecondsLeft(null);
    setLabel(null);
  }, [stopTimers]);

  // Leaving sends it now: the page being hidden or closed, or this screen going away.
  useEffect(() => {
    const flush = () => void send();
    const onHide = () => {
      if (document.visibilityState === "hidden") flush();
    };
    document.addEventListener("visibilitychange", onHide);
    window.addEventListener("pagehide", flush);
    return () => {
      document.removeEventListener("visibilitychange", onHide);
      window.removeEventListener("pagehide", flush);
      flush();
    };
  }, [send]);

  // Escape undoes a decision that is waiting.
  useEffect(() => {
    if (secondsLeft === null) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.preventDefault(); // undoing uses the key; it must not also leave the page
      undo();
    };
    document.addEventListener("keydown", onKey, true);
    return () => document.removeEventListener("keydown", onKey, true);
  }, [secondsLeft, undo]);

  return {
    /** Set while a decision is waiting to be sent. */
    waiting: secondsLeft !== null,
    label,
    secondsLeft,
    /** Set while the request is in flight. */
    saving,
    start,
    undo,
  };
}
