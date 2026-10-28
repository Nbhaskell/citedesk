import { describe, expect, it } from "vitest";
import tokensCss from "./tokens.css?raw";

function colours(): Record<string, string> {
  const found: Record<string, string> = {};
  for (const match of tokensCss.matchAll(/--([a-z0-9-]+):\s*(#[0-9a-f]{6})\b/gi)) {
    found[match[1] as string] = match[2] as string;
  }
  return found;
}

function luminance(hex: string): number {
  const channel = (start: number) => {
    const value = parseInt(hex.slice(start, start + 2), 16) / 255;
    return value <= 0.03928 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * channel(1) + 0.7152 * channel(3) + 0.0722 * channel(5);
}

function contrast(a: string, b: string): number {
  const [light, dark] = [luminance(a), luminance(b)].sort((x, y) => y - x) as [number, number];
  return (light + 0.05) / (dark + 0.05);
}

const palette = colours();
const pick = (name: string): string => {
  const value = palette[name];
  if (!value) throw new Error(`token --${name} is missing`);
  return value;
};

// [foreground, background]: WCAG 2.1 AA needs 4.5 for text.
const TEXT_PAIRS: [string, string][] = [
  ["ink", "paper"],
  ["ink", "sheet"],
  ["slate", "paper"],
  ["slate", "sheet"],
  ["patina", "paper"],
  ["patina", "sheet"],
  ["sheet", "patina"],
  ["patina", "patina-mist"],
  ["sheet", "signal"],
  ["signal-ink", "signal-tint"],
  ["amber-ink", "amber-tint"],
  ["slate-ink", "slate-tint"],
  ["pass-ink", "pass-tint"],
  ["ink", "mark"],
];

// Boundaries, bands and the focus ring need 3 against what they sit on.
const NON_TEXT_PAIRS: [string, string][] = [
  ["edge", "paper"],
  ["edge", "sheet"],
  ["ring", "paper"],
  ["ring", "sheet"],
  ["signal", "paper"],
  ["amber", "paper"],
];

describe("design tokens", () => {
  it.each(TEXT_PAIRS)("text %s on %s has at least 4.5:1", (fg, bg) => {
    expect(contrast(pick(fg), pick(bg))).toBeGreaterThanOrEqual(4.5);
  });

  it.each(NON_TEXT_PAIRS)("%s against %s has at least 3:1", (fg, bg) => {
    expect(contrast(pick(fg), pick(bg))).toBeGreaterThanOrEqual(3);
  });

  it("uses the values the design plan names", () => {
    expect(palette).toMatchObject({
      paper: "#f3f5f3",
      ink: "#1f2a30",
      patina: "#0d5c57",
      signal: "#b3261e",
      ring: "#1d5fd1",
    });
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
});
