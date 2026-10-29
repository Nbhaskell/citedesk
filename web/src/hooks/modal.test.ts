import { afterEach, describe, expect, it } from "vitest";
import { modalOpen, setModalOpen } from "./modal";
import { shortcutKey } from "./shortcuts";

afterEach(() => {
  setModalOpen(false);
  window.localStorage.clear();
});

const press = (key: string) => {
  const event = new KeyboardEvent("keydown", { key, bubbles: true, cancelable: true });
  document.body.dispatchEvent(event);
  return event;
};

describe("a modal dialog being open", () => {
  it("is off until one is opened", () => {
    expect(modalOpen()).toBe(false);
    setModalOpen(true);
    expect(modalOpen()).toBe(true);
    setModalOpen(false);
    expect(modalOpen()).toBe(false);
  });

  it("silences every single-key shortcut, so a key meant for the dialog does nothing behind it", () => {
    expect(shortcutKey(press("a"))).toBe("a");
    setModalOpen(true);
    expect(shortcutKey(press("a"))).toBeNull();
    expect(shortcutKey(press("j"))).toBeNull();
    setModalOpen(false);
    expect(shortcutKey(press("j"))).toBe("j");
  });
});
