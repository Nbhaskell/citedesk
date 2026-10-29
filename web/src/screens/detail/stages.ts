/** A pipeline stage as a phrase that finishes "it failed while ...". */
const STAGES: Record<string, string> = {
  screen: "checking the message",
  understand: "reading the message",
  route: "deciding what to do",
  retrieve: "looking up your documents",
  draft: "writing the draft",
  check: "checking the draft",
};

export function stageLabel(stage: string): string {
  return STAGES[stage] ?? "working on it";
}
