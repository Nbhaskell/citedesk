import { forwardRef, useCallback, useState } from "react";
import type { Draft, DraftCheck } from "../../api/types";
import { detail as words } from "../../copy";
import { ungroundedFigures } from "./checks";
import { highlight } from "./sources";
import { Marked } from "./parts";
import styles from "./Detail.module.css";

export const MAX_EDITED_CHARS = 10_000;

const storageKey = (draftId: number) => `citedesk.draft.${draftId}`;

// An unsent edit is kept in the browser while typing, so closing the tab does not lose it. It is
// removed when a decision lands. A blocked or missing store just means nothing is kept.
function readSaved(draftId: number): string | null {
  try {
    return window.localStorage.getItem(storageKey(draftId));
  } catch {
    return null;
  }
}

function writeSaved(draftId: number, original: string, text: string): void {
  try {
    if (text === original) window.localStorage.removeItem(storageKey(draftId));
    else window.localStorage.setItem(storageKey(draftId), text);
  } catch {
    // Not kept; the text on screen is still there.
  }
}

export function forgetSaved(draftId: number): void {
  try {
    window.localStorage.removeItem(storageKey(draftId));
  } catch {
    // Nothing to forget.
  }
}

/** The text being edited, saved as the person types. Use `key={draft.id}` so a new draft starts fresh. */
export function useDraftText(draft: Draft) {
  const [text, setText] = useState(() => readSaved(draft.id) ?? draft.body);
  const change = useCallback(
    (next: string) => {
      setText(next);
      writeSaved(draft.id, draft.body, next);
    },
    [draft.id, draft.body],
  );
  return { text, change, edited: text.trim() !== draft.body.trim() };
}

export function wordCount(text: string): number {
  return text.trim() === "" ? 0 : text.trim().split(/\s+/).length;
}

/** The reply as an editable text area, with the subject above it and a word count below. */
export const DraftEditor = forwardRef<
  HTMLTextAreaElement,
  {
    draft: Draft;
    text: string;
    onChange: (text: string) => void;
    maxWords: number;
    disabled: boolean;
  }
>(function DraftEditor({ draft, text, onChange, maxWords, disabled }, ref) {
  const count = wordCount(text);
  return (
    <div>
      <p className={styles.meta}>{words.draft.kind[draft.kind]}</p>
      {draft.subject ? (
        <p>
          <span className={styles.label}>{words.draft.subject}</span>{" "}
          <span className={styles.subject}>{draft.subject}</span>
        </p>
      ) : null}
      <label htmlFor="draft-body" className={styles.label}>
        {words.draft.body}
      </label>
      <textarea
        id="draft-body"
        ref={ref}
        className={styles.editor}
        value={text}
        rows={12}
        maxLength={MAX_EDITED_CHARS}
        onChange={(event) => onChange(event.target.value)}
        disabled={disabled}
        aria-describedby="draft-count draft-note"
      />
      <p id="draft-count" className={count > maxWords ? styles.over : styles.meta}>
        {words.draft.words(count, maxWords)}
      </p>
      <p id="draft-note" className={styles.meta}>
        {words.draft.editNote}
      </p>
    </div>
  );
});

/** A draft that is not being edited: for a blocked draft, a reference copy or a rejected one. */
export function DraftView({ draft, checks }: { draft: Draft; checks: DraftCheck[] }) {
  const figures = ungroundedFigures(checks);
  return (
    <div>
      {draft.subject ? (
        <p>
          <span className={styles.label}>{words.draft.subject}</span>{" "}
          <span className={styles.subject}>{draft.subject}</span>
        </p>
      ) : null}
      <p className={styles.prose}>
        <Marked segments={highlight(draft.body, figures)} />
      </p>
    </div>
  );
}
