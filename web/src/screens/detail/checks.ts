import type { CheckCode, DraftCheck } from "../../api/types";
import { check as checkWords, reasonFromCheck } from "../../copy";

export interface CheckView {
  code: CheckCode;
  blocking: boolean;
  passed: boolean;
  title: string;
  /** Short sentences saying what was found. Plain text. */
  lines: string[];
}

function strings(detail: DraftCheck["detail"], key: string): string[] {
  const value = detail?.[key];
  return Array.isArray(value) ? value.filter((v): v is string => typeof v === "string") : [];
}

function flag(detail: DraftCheck["detail"], key: string): boolean {
  return detail?.[key] === true;
}

function number(detail: DraftCheck["detail"], key: string): number | null {
  const value = detail?.[key];
  return typeof value === "number" ? value : null;
}

const humanise = (name: string): string => name.replace(/_/g, " ");

/** What a check found, as sentences. What each detail key means is in `citedesk/checks.py`. */
function linesFor(check: DraftCheck): string[] {
  const { detail } = check;
  const lines: string[] = [];
  switch (check.check_code) {
    case "FIGURES_GROUNDED": {
      const ungrounded = strings(detail, "ungrounded");
      const derived = strings(detail, "derived");
      const grounded = strings(detail, "grounded");
      if (ungrounded.length) lines.push(`Not in your documents: ${ungrounded.join(", ")}`);
      if (derived.length) {
        lines.push(`Added up from your documents, so check the sum: ${derived.join(", ")}`);
      }
      if (grounded.length && check.passed) {
        lines.push(`Found in your documents: ${grounded.join(", ")}`);
      }
      break;
    }
    case "NO_COMMITMENT": {
      const matched = strings(detail, "matched_patterns");
      if (matched.length) lines.push(`Promises found: ${matched.map(humanise).join(", ")}`);
      break;
    }
    case "STRUCTURE": {
      const missing = strings(detail, "missing");
      if (missing.includes("greeting")) lines.push("No greeting at the start");
      if (missing.includes("sign_off")) lines.push("No sign-off at the end");
      const words = number(detail, "words");
      const max = number(detail, "max_words");
      if (words !== null && max !== null && words > max) {
        lines.push(`${words} words; the limit is ${max}`);
      }
      const jargon = strings(detail, "jargon");
      if (jargon.length) lines.push(`Wording from the system: ${jargon.join(", ")}`);
      break;
    }
    case "CLAIMS_HAVE_SOURCES": {
      const bad = detail?.["bad_indices"];
      if (Array.isArray(bad) && bad.length) {
        lines.push("A fact points to a passage that does not exist");
      }
      if (flag(detail, "no_claims")) lines.push("The draft states facts but names no passage");
      break;
    }
    case "NO_INJECTION_ECHO": {
      if (flag(detail, "system_prompt_echo")) lines.push("Repeats the system's own instructions");
      if (strings(detail, "injection_patterns").length) {
        lines.push("Contains wording that tries to give instructions");
      }
      const links = strings(detail, "foreign_links");
      if (links.length) lines.push(`Links that are not in your documents: ${links.join(", ")}`);
      break;
    }
    case "ADDRESSES_ASK":
      break;
  }
  return lines;
}

/**
 * The checks as the reviewer reads them: failed blocking ones first, then failed warnings, then
 * passes. A check that is not implemented (`ADDRESSES_ASK`) is not shown.
 */
export function describeChecks(checks: DraftCheck[]): CheckView[] {
  const rank = (c: CheckView) => (c.passed ? 2 : c.blocking ? 0 : 1);
  return checks
    .filter((c) => c.check_code !== "ADDRESSES_ASK")
    .map((c) => ({
      code: c.check_code,
      blocking: c.blocking,
      passed: c.passed,
      title: checkWords[c.check_code],
      lines: linesFor(c),
    }))
    .sort((a, b) => rank(a) - rank(b));
}

/** Figures the figure check could not find in the documents, as they appear in the draft. */
export function ungroundedFigures(checks: DraftCheck[]): string[] {
  const figures = checks.find((c) => c.check_code === "FIGURES_GROUNDED" && !c.passed);
  return strings(figures?.detail ?? null, "ungrounded");
}

/** Figures that were found in the documents, to mark in the source passages. */
export function groundedFigures(checks: DraftCheck[]): string[] {
  const figures = checks.find((c) => c.check_code === "FIGURES_GROUNDED");
  return strings(figures?.detail ?? null, "grounded");
}

/** The sentence at the top of a draft that failed a check that must pass. */
export function blockedNotice(checks: DraftCheck[]): string | null {
  const failed = checks.find((c) => c.blocking && !c.passed);
  if (!failed) return null;
  if (failed.check_code === "FIGURES_GROUNDED") {
    const figures = ungroundedFigures(checks);
    if (figures.length === 0)
      return "Not ready: a price or date in the draft isn't in your documents.";
    return `Not ready: ${figures.join(", ")} ${figures.length > 1 ? "aren't" : "isn't"} in your documents.`;
  }
  if (failed.check_code === "NO_COMMITMENT") {
    return `Not ready: ${reasonFromCheck.POLICY_EXCEPTION_REQUEST}.`;
  }
  return `Not ready: ${reasonFromCheck.INJECTION_SUSPECTED}.`;
}
