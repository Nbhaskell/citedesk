// The arithmetic and wording of the Insights figures, kept out of the component so it can be
// tested on its own. Nothing here touches customer text: it only ever sees counts and times.
import { dayText } from "../../lib/age";

/** Below this many approved replies a share is not shown: 3 of 4 is not "75%". */
export const MIN_SAMPLE = 10;

const STORAGE_KEY = "citedesk.minutesWithoutTool";
const MAX_MINUTES = 24 * 60;

export interface Counted {
  code: string;
  count: number;
}

export function countOf(list: Counted[], code: string): number {
  return list.find((entry) => entry.code === code)?.count ?? 0;
}

/** Replies a person approved, as written or after editing. A rejection is not one. */
export function approvedCount(decisions: Counted[]): number {
  return countOf(decisions, "approve") + countOf(decisions, "edit_approve");
}

export function percent(share: number): string {
  return `${Math.round(share * 100)}%`;
}

export function formatDuration(seconds: number): string {
  const whole = Math.round(seconds);
  if (whole < 1) return "under 1 second";
  if (whole < 60) return whole === 1 ? "1 second" : `${whole} seconds`;
  if (whole < 3600) {
    const minutes = Math.floor(whole / 60);
    const rest = whole % 60;
    return rest ? `${minutes} min ${rest} s` : `${minutes} min`;
  }
  const hours = Math.floor(whole / 3600);
  const minutes = Math.floor((whole % 3600) / 60);
  return minutes ? `${hours} h ${minutes} min` : `${hours} h`;
}

export function formatMinutes(minutes: number): string {
  const whole = Math.round(minutes);
  if (whole < 60) return `${whole} min`;
  const hours = Math.floor(whole / 60);
  const rest = whole % 60;
  return rest ? `${hours} h ${rest} min` : `${hours} h`;
}

/** "20 Oct 2026 to 28 Oct 2026", or one day when the first and last arrival share it. */
export function periodText(start: string | null, end: string | null): string {
  if (!start || !end) return "";
  const from = dayText(start);
  const to = dayText(end);
  if (!from || !to) return "";
  return from === to ? from : `${from} to ${to}`;
}

/** The assumption as a number of minutes, or null when it is not a sensible one. */
export function parseMinutes(text: string): number | null {
  const trimmed = text.trim().replace(",", ".");
  if (!/^\d+(\.\d+)?$/.test(trimmed)) return null;
  const minutes = Number(trimmed);
  return minutes > 0 && minutes <= MAX_MINUTES ? minutes : null;
}

/**
 * What the replies saved: each one took the median review time instead of the assumed time
 * without the tool. A review slower than the assumption saves nothing, never a negative.
 */
export function savedMinutes(
  approved: number,
  minutesWithout: number | null,
  medianReviewSeconds: number | null,
): number | null {
  if (approved <= 0 || minutesWithout === null || medianReviewSeconds === null) return null;
  return approved * Math.max(0, minutesWithout - medianReviewSeconds / 60);
}

// The assumption is the person's own number. It stays in this browser and is never sent anywhere.
export function loadAssumption(): string {
  try {
    return window.localStorage.getItem(STORAGE_KEY) ?? "";
  } catch {
    return "";
  }
}

export function saveAssumption(text: string): void {
  try {
    if (text === "") window.localStorage.removeItem(STORAGE_KEY);
    else window.localStorage.setItem(STORAGE_KEY, text);
  } catch {
    // Not kept after this visit; the figure still works while the page is open.
  }
}
