const MINUTE = 60;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

/**
 * How long ago something arrived, in the words a person uses. Past a month it is the date: a
 * message imported with an old date should not read "5 months ago" as if that were useful.
 */
export function ageText(iso: string, now: number = Date.now()): string {
  const then = Date.parse(iso);
  if (Number.isNaN(then)) return "";
  const seconds = Math.max(0, Math.floor((now - then) / 1000));
  if (seconds < MINUTE) return "just now";
  if (seconds < HOUR) return `${Math.floor(seconds / MINUTE)} min ago`;
  if (seconds < DAY) return `${Math.floor(seconds / HOUR)} h ago`;
  const days = Math.floor(seconds / DAY);
  if (days < 30) return days === 1 ? "1 day ago" : `${days} days ago`;
  return new Date(then).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
}

/** The exact time, for a tooltip and for anyone who wants more than "4 min ago". */
export function exactText(iso: string): string {
  const then = Date.parse(iso);
  return Number.isNaN(then)
    ? ""
    : new Date(then).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" });
}
