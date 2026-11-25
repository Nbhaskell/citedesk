import { describe, expect, it } from "vitest";
import citeCss from "./cite-tokens.css?raw";
import tokensCss from "./tokens.css?raw";

// Every CSS file of the app except the shared tokens: colours come only from --cite-* names.
const appCss = import.meta.glob<string>(["../**/*.css", "!./cite-tokens.css"], {
  query: "?raw",
  import: "default",
  eager: true,
});

function colours(block: string): Record<string, string> {
  const found: Record<string, string> = {};
  for (const match of block.matchAll(/--cite-([a-z0-9-]+):\s*(#[0-9a-f]{6})\b/gi)) {
    found[match[1] as string] = match[2] as string;
  }
  return found;
}

// The light values are the first :root block; the forced dark block holds every dark value.
const light = colours(citeCss.slice(0, citeCss.indexOf("@media")));
const dark = { ...light, ...colours(citeCss.slice(citeCss.indexOf(':root[data-theme="dark"]'))) };

function luminance(hex: string): number {
  const channel = (start: number) => {
    const value = parseInt(hex.slice(start, start + 2), 16) / 255;
    return value <= 0.03928 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * channel(1) + 0.7152 * channel(3) + 0.0722 * channel(5);
}

function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x) as [number, number];
  return (hi + 0.05) / (lo + 0.05);
}

// [foreground, background] pairs this app puts together. WCAG 2.1 AA needs 4.5 for text.
const TEXT_PAIRS: [string, string][] = [
  ["text", "canvas"],
  ["text", "surface"],
  ["muted", "canvas"],
  ["muted", "surface"],
  ["muted", "warning-bg"],
  ["link", "canvas"],
  ["link", "surface"],
  ["on-primary", "primary"],
  ["on-primary", "primary-hover"],
  ["on-primary", "danger-solid"],
  ["danger-text", "danger-bg"],
  ["danger-text", "surface"],
  ["warning-text", "warning-bg"],
  ["info-text", "info-bg"],
  ["neutral-text", "neutral-bg"],
  ["success-text", "surface"],
  ["muted", "rule"],
  ["text", "danger-bg"],
  ["muted", "danger-bg"],
  ["link", "info-bg"],
];

// Boundaries of controls and the focus ring need 3 against what they sit on. Controls have a
// Surface fill, so their border is checked against Surface (input-border on canvas is 2.92:1 in light).
const NON_TEXT_PAIRS: [string, string][] = [
  ["input-border", "surface"],
  ["focus", "surface"],
  ["focus", "canvas"],
];

describe.each([
  ["light", light],
  ["dark", dark],
])("Cite tokens, %s theme", (_theme, palette) => {
  const pick = (name: string): string => {
    const value = palette[name];
    if (!value) throw new Error(`token --cite-${name} is missing`);
    return value;
  };

  it.each(TEXT_PAIRS)("text %s on %s has at least 4.5:1", (fg, bg) => {
    expect(contrast(pick(fg), pick(bg))).toBeGreaterThanOrEqual(4.5);
  });

  it.each(NON_TEXT_PAIRS)("%s against %s has at least 3:1", (fg, bg) => {
    expect(contrast(pick(fg), pick(bg))).toBeGreaterThanOrEqual(3);
  });
});

describe("app styles", () => {
  it("reads every app CSS file", () => {
    expect(Object.keys(appCss).length).toBeGreaterThan(5);
  });

  it.each(Object.entries(appCss))("%s types no colour value", (_path, css) => {
    expect(css.match(/#[0-9a-f]{3,8}\b|rgba?\(|hsla?\(/gi)).toBeNull();
  });

  it("sets no text smaller than 16px", () => {
    const sizes = [...tokensCss.matchAll(/--size-[a-z]+:\s*([\d.]+)rem/g)].map(
      (m) => Number(m[1]) * 16,
    );
    expect(sizes.length).toBeGreaterThan(0);
    for (const size of sizes) expect(size).toBeGreaterThanOrEqual(16);
  });

  it("keeps the touch target at 44px", () => {
    const match = /--target:\s*([\d.]+)rem/.exec(tokensCss);
    expect(Number(match?.[1]) * 16).toBeGreaterThanOrEqual(44);
  });

  it("uses no Cite type size below 16px", () => {
    for (const css of Object.values(appCss)) {
      expect(css).not.toMatch(/--cite-text-(label|small|button|body|title)\b/);
    }
  });
});
