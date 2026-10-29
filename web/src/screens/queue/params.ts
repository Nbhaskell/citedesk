import type { InquiryQuery } from "../../api/client";
import type { InquiryStatus } from "../../api/types";

export const FILTERS = ["review", "escalated", "failed", "archived", "all"] as const;
export type Filter = (typeof FILTERS)[number];
export const DEFAULT_FILTER: Filter = "review";

const STATUSES: Record<Filter, InquiryStatus[] | undefined> = {
  review: ["needs_review"],
  escalated: ["escalated"],
  failed: ["failed"],
  archived: ["archived"],
  all: undefined,
};

/** The three states that need a person: what the header's urgent count is counted over. */
export const ATTENTION: InquiryStatus[] = ["needs_review", "escalated", "failed"];

/**
 * What the queue shows. Only codes live in the address (`show`, `urgency`); the search text is
 * page state and is never written to the URL (docs/UI_DESIGN_PLAN.md section 6).
 */
export interface QueueView {
  /** The chosen filter, or null when none was chosen (the default, or "urgent only"). */
  filter: Filter | null;
  urgentOnly: boolean;
  q: string;
}

export function parseView(params: URLSearchParams, q = ""): QueueView {
  const show = params.get("show");
  const filter = FILTERS.find((f) => f === show) ?? null;
  return { filter, urgentOnly: params.get("urgency") === "urgent", q: q.trim() };
}

/**
 * The statuses in effect: a chosen filter, else "urgent only" widens to every state that needs a
 * person, else the default tab.
 */
export function effectiveStatuses(view: QueueView): InquiryStatus[] | undefined {
  if (view.filter) return STATUSES[view.filter];
  return view.urgentOnly ? ATTENTION : STATUSES[DEFAULT_FILTER];
}

export function toQuery(view: QueueView): InquiryQuery {
  const query: InquiryQuery = {};
  const status = effectiveStatuses(view);
  if (status) query.status = status;
  if (view.urgentOnly) query.urgency = ["urgent"];
  if (view.q) query.q = view.q;
  return query;
}

/** The address for a view: only what differs from the default. */
export function viewToSearch(view: Pick<QueueView, "filter" | "urgentOnly">): string {
  const params = new URLSearchParams();
  if (view.filter && view.filter !== DEFAULT_FILTER) params.set("show", view.filter);
  if (view.urgentOnly) params.set("urgency", "urgent");
  const text = params.toString();
  return text ? `?${text}` : "";
}

/** The tab to mark as current, or null when "urgent only" is showing a wider set. */
export function currentTab(view: QueueView): Filter | null {
  if (view.filter) return view.filter;
  return view.urgentOnly ? null : DEFAULT_FILTER;
}
