import type { Retrieval, Source } from "../../api/types";

/**
 * The passages a draft was written from, in the order the backend merged them: those of answered
 * questions only, without repeats. A claim's `source_index` points into this list, so the order
 * must match `citedesk/retrieval.py: merged_sources`.
 */
export function mergedSources(retrievals: Retrieval[]): Source[] {
  const merged: Source[] = [];
  for (const row of retrievals) {
    if (row.declined) continue;
    for (const source of row.sources) {
      const same = merged.some(
        (m) =>
          m.file === source.file &&
          m.section === source.section &&
          m.page === source.page &&
          m.text === source.text,
      );
      if (!same) merged.push(source);
    }
  }
  return merged;
}

export interface Segment {
  text: string;
  marked: boolean;
}

/**
 * Split text into pieces, marking every occurrence of a needle. The page renders the pieces as
 * text, so nothing from the draft or a passage is ever treated as markup. Longer needles win where
 * they overlap; empty needles are ignored.
 */
export function highlight(text: string, needles: string[]): Segment[] {
  const wanted = [...new Set(needles.filter((n) => n.length > 0))].sort(
    (a, b) => b.length - a.length,
  );
  if (wanted.length === 0) return text ? [{ text, marked: false }] : [];
  const ranges: [number, number][] = [];
  for (const needle of wanted) {
    let from = 0;
    for (;;) {
      const at = text.indexOf(needle, from);
      if (at < 0) break;
      const end = at + needle.length;
      if (!ranges.some(([a, b]) => at < b && end > a)) ranges.push([at, end]);
      from = end;
    }
  }
  ranges.sort((x, y) => x[0] - y[0]);
  const segments: Segment[] = [];
  let cursor = 0;
  for (const [start, end] of ranges) {
    if (start > cursor) segments.push({ text: text.slice(cursor, start), marked: false });
    segments.push({ text: text.slice(start, end), marked: true });
    cursor = end;
  }
  if (cursor < text.length) segments.push({ text: text.slice(cursor), marked: false });
  return segments;
}
