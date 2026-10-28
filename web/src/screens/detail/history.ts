import type { AuditEvent } from "../../api/types";
import { check as checkWords, status as statusWords } from "../../copy";
import { stageLabel } from "./stages";

const DECISIONS: Record<string, string> = {
  approve: "Approved by a reviewer",
  edit_approve: "Edited and approved by a reviewer",
  reject: "Rejected by a reviewer",
  escalate: "Escalated by a reviewer",
  resolve: "Marked resolved by a reviewer",
};

const MOVES: Partial<Record<AuditEvent["to_status"] & string, string>> = {
  screened: "Message checked",
  classified: "Message read",
  routed: "Next step decided",
  drafted: "Draft written",
  needs_review: "Ready for review",
  escalated: "Escalated",
  approved: "Reply approved",
  rejected: "Draft rejected",
  exported: "Reply copied",
  resolved: "Marked resolved",
  archived: "Archived",
  failed: "Failed",
};

const list = (value: unknown): string[] =>
  Array.isArray(value) ? value.filter((v): v is string => typeof v === "string") : [];

/**
 * One line of history in plain words, or null for an event that adds nothing a reviewer needs
 * (a stage starting, a decision about the route). Built from codes only: an event never holds
 * message text.
 */
export function describeEvent(event: AuditEvent): string | null {
  switch (event.event_type) {
    case "status_changed": {
      if (event.from_status === "failed") {
        const stage =
          typeof event.payload["retry_of_stage"] === "string"
            ? event.payload["retry_of_stage"]
            : null;
        return stage ? `Retried from ${stageLabel(stage)}` : "Retried";
      }
      const to = event.to_status;
      if (!to || to === "needs_review") return null; // the check line says it
      return MOVES[to] ?? statusWords[to];
    }
    case "review_recorded": {
      const decision = event.payload["decision"];
      return typeof decision === "string" ? (DECISIONS[decision] ?? null) : null;
    }
    case "check_failed": {
      const code = event.payload["check"];
      const words = typeof code === "string" ? checkWords[code as keyof typeof checkWords] : null;
      return words ? `Check failed: ${words}` : "A check failed";
    }
    case "stage_failed":
      return event.stage ? `Failed while ${stageLabel(event.stage)}` : "A step failed";
    case "stage_finished": {
      if (event.stage === "draft" && event.payload["redraft"] === true) return "New draft written";
      if (event.stage !== "check") return null;
      if (list(event.payload["blocking_failed"]).length > 0) return null;
      return list(event.payload["warnings_failed"]).length > 0
        ? "Checked: passed, with notes"
        : "Checked: all passed";
    }
    default:
      return null;
  }
}

export interface HistoryLine {
  id: number;
  at: string;
  text: string;
}

export function historyLines(events: AuditEvent[]): HistoryLine[] {
  return [...events]
    .sort((a, b) => a.id - b.id)
    .flatMap((event) => {
      const text = describeEvent(event);
      return text ? [{ id: event.id, at: event.created_at, text }] : [];
    });
}
