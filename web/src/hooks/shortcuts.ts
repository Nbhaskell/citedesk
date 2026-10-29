// Single-key shortcuts (j, k, a, ...) are off while a text field has focus, and can be switched
// off for good: WCAG 2.1.4 (character key shortcuts). The switch is a per-browser convenience, so
// a blocked or empty store means "on", never an error.
import { modalOpen } from "./modal";

const STORAGE_KEY = "citedesk.shortcuts";

export function shortcutsEnabled(): boolean {
  try {
    return window.localStorage.getItem(STORAGE_KEY) !== "off";
  } catch {
    return true;
  }
}

export function setShortcutsEnabled(on: boolean): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, on ? "on" : "off");
  } catch {
    // The setting is not kept; the shortcuts stay as they were for this visit.
  }
}

/** True when a key press is meant for typing, or for a control that uses the key itself. */
export function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  if (target.isContentEditable) return true;
  return ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName);
}

/** The key if this event is a plain shortcut press that should be acted on, otherwise null. */
export function shortcutKey(event: KeyboardEvent): string | null {
  if (event.defaultPrevented || event.ctrlKey || event.metaKey || event.altKey) return null;
  if (isTypingTarget(event.target) || !shortcutsEnabled() || modalOpen()) return null;
  return event.key;
}
