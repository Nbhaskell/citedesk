import { axe } from "jest-axe";
import { expect } from "vitest";

/** Fails with the rule names and help text of every accessibility violation found. */
export async function expectAccessible(container: Element): Promise<void> {
  const results = await axe(container);
  expect(results.violations.map((v) => `${v.id}: ${v.help}`)).toEqual([]);
}
