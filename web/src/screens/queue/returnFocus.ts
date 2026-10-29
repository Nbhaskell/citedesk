// When the person goes back from an inquiry to the queue, focus returns to the row they were on,
// so a keyboard user carries on from where they were. The inquiry screen notes which one it
// showed; the queue takes the note once it has its rows. Kept in memory: it is only meaningful
// for the next visit to the queue.
let viewed: number | null = null;

export function markViewed(id: number): void {
  viewed = id;
}

/** The inquiry last viewed, once: asking clears it. */
export function takeViewed(): number | null {
  const id = viewed;
  viewed = null;
  return id;
}

export function forgetViewed(): void {
  viewed = null;
}
