import { afterEach, describe, expect, it, vi } from "vitest";
import { isTypingTarget, setShortcutsEnabled, shortcutKey, shortcutsEnabled } from "./shortcuts";

afterEach(() => window.localStorage.clear());

function press(key: string, init: KeyboardEventInit = {}, target?: HTMLElement): KeyboardEvent {
  const event = new KeyboardEvent("keydown", { key, bubbles: true, cancelable: true, ...init });
  (target ?? document.body).dispatchEvent(event);
  return event;
}

describe("shortcuts", () => {
  it("are on unless switched off", () => {
    expect(shortcutsEnabled()).toBe(true);
    setShortcutsEnabled(false);
    expect(shortcutsEnabled()).toBe(false);
    setShortcutsEnabled(true);
    expect(shortcutsEnabled()).toBe(true);
  });

  it("stay on, and do not throw, when the browser blocks storage", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    expect(shortcutsEnabled()).toBe(true);
    expect(() => setShortcutsEnabled(false)).not.toThrow();
  });

  it("recognise typing targets", () => {
    for (const tag of ["input", "textarea", "select"]) {
      expect(isTypingTarget(document.createElement(tag))).toBe(true);
    }
    expect(isTypingTarget(document.createElement("button"))).toBe(false);
    expect(isTypingTarget(null)).toBe(false);
  });

  it("give the key for a plain press and nothing for the rest", () => {
    let seen: (string | null)[] = [];
    const listener = (e: KeyboardEvent) => seen.push(shortcutKey(e));
    document.addEventListener("keydown", listener);
    press("j");
    press("j", { ctrlKey: true });
    press("j", { metaKey: true });
    press("j", { altKey: true });
    const field = document.body.appendChild(document.createElement("input"));
    press("j", {}, field);
    setShortcutsEnabled(false);
    press("j");
    document.removeEventListener("keydown", listener);
    field.remove();
    expect(seen).toEqual(["j", null, null, null, null, null]);
    seen = [];
  });
});
