// "Next" and "previous" on an inquiry mean the list the person opened it from. The queue hands
// that list along as router state (ids only, never text), so a page opened from a link or a
// bookmark has no list and offers no next or previous.
const MAX_IDS = 1000;

/** The router state a queue row sends with its link. */
export interface QueueState {
  queue: number[];
}

// One shared empty list, so "no list" is the same value on every render.
const NONE: number[] = [];

/** The ids carried in router state, or an empty list if the state is anything else. */
export function readQueueState(state: unknown): number[] {
  if (typeof state !== "object" || state === null || !("queue" in state)) return NONE;
  const queue = (state as { queue: unknown }).queue;
  if (!Array.isArray(queue) || queue.length > MAX_IDS) return NONE;
  return queue.every((id) => Number.isInteger(id) && id > 0) ? (queue as number[]) : NONE;
}

export interface Neighbours {
  previous: number | null;
  next: number | null;
  /** 1-based place of this inquiry in the list. */
  position: number;
  total: number;
}

export function neighbours(ids: number[], id: number): Neighbours | null {
  const at = ids.indexOf(id);
  if (at < 0 || ids.length < 2) return null;
  return {
    previous: at > 0 ? (ids[at - 1] ?? null) : null,
    next: at < ids.length - 1 ? (ids[at + 1] ?? null) : null,
    position: at + 1,
    total: ids.length,
  };
}
