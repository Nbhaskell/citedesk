import { useEffect, useRef, useState } from "react";
import type { InquiryDetail, Source } from "../../api/types";
import { actions, detail as words } from "../../copy";
import { shortcutKey } from "../../hooks/shortcuts";
import { DraftEditor, forgetSaved, useDraftText } from "./draft";
import { ErrorNote, InlineForm } from "./forms";
import { ChecksPanel, ClaimList, Panel } from "./parts";
import type { Decisions } from "./useDecisions";
import { usePendingDecision } from "./usePendingDecision";
import styles from "./Detail.module.css";

const MAX_SECONDS = 86_400;

/**
 * The inquiry is waiting for a person: an editable draft, its checks, and the three decisions.
 * Approve and reject wait five seconds, visibly, so they can be undone. Escalating is sent at once.
 * Keys: a approve, e edit, r reject, x escalate (never while typing, and switchable off).
 */
export function ReviewPanel({
  detail,
  decisions,
  maxWords,
  sources,
  onOpenSource,
}: {
  detail: InquiryDetail;
  decisions: Decisions;
  maxWords: number;
  sources: Source[];
  onOpenSource: (index: number) => void;
}) {
  const draft = detail.draft;
  if (!draft) return null;
  return (
    <ReviewBody
      key={draft.id}
      detail={detail}
      draft={draft}
      decisions={decisions}
      maxWords={maxWords}
      sources={sources}
      onOpenSource={onOpenSource}
    />
  );
}

function ReviewBody({
  detail,
  draft,
  decisions,
  maxWords,
  sources,
  onOpenSource,
}: {
  detail: InquiryDetail;
  draft: NonNullable<InquiryDetail["draft"]>;
  decisions: Decisions;
  maxWords: number;
  sources: Source[];
  onOpenSource: (index: number) => void;
}) {
  const { text, change, edited } = useDraftText(draft);
  const pending = usePendingDecision();
  const editor = useRef<HTMLTextAreaElement>(null);
  const [openedAt] = useState(() => Date.now());
  const [panel, setPanel] = useState<"reject" | "escalate" | null>(null);
  const [reason, setReason] = useState("");
  const [note, setNote] = useState("");
  const [missing, setMissing] = useState(false);

  const locked = pending.waiting || pending.saving || decisions.busy !== null;
  const seconds = () => Math.min(MAX_SECONDS, Math.round((Date.now() - openedAt) / 1000));
  const approveLabel = edited ? actions.approveEdited : actions.approve;

  const approve = () => {
    if (locked) return;
    decisions.clearError();
    const body = edited
      ? { edited_body: text, review_seconds: seconds() }
      : { review_seconds: seconds() };
    pending.start(approveLabel.done, async () => {
      const saved = await decisions.approve(draft.id, body);
      if (saved) forgetSaved(draft.id);
      return saved;
    });
  };

  const reject = () => {
    if (reason.trim() === "") {
      setMissing(true);
      return;
    }
    setMissing(false);
    setPanel(null);
    const why = reason.trim();
    pending.start(actions.reject.done, async () => {
      const saved = await decisions.reject(draft.id, { reason: why, review_seconds: seconds() });
      if (!saved) setPanel("reject");
      return saved;
    });
  };

  const escalate = async () => {
    if (note.trim() === "") {
      setMissing(true);
      return;
    }
    setMissing(false);
    if (await decisions.escalate(detail.inquiry.id, note.trim())) setPanel(null);
  };

  const open = (which: "reject" | "escalate") => {
    if (locked) return;
    decisions.clearError();
    setMissing(false);
    setPanel(which);
  };

  // Keyboard: a, e, r, x. Kept current without re-adding the listener on every keystroke.
  const handlers = useRef({ approve, open });
  useEffect(() => {
    handlers.current = { approve, open };
  });
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape" && panel && !pending.waiting) {
        setPanel(null);
        event.preventDefault();
        return;
      }
      const key = shortcutKey(event);
      if (key === "a") handlers.current.approve();
      else if (key === "e") editor.current?.focus();
      else if (key === "r") handlers.current.open("reject");
      else if (key === "x") handlers.current.open("escalate");
      else return;
      event.preventDefault();
    };
    // Capture phase, so Escape closes the form before the screen treats it as "go back".
    document.addEventListener("keydown", onKey, true);
    return () => document.removeEventListener("keydown", onKey, true);
  }, [panel, pending.waiting]);

  return (
    <>
      <Panel title={words.sections.draft}>
        <DraftEditor
          ref={editor}
          draft={draft}
          text={text}
          onChange={change}
          maxWords={maxWords}
          disabled={locked}
        />
        <ClaimList claims={draft.claims} sourceCount={sources.length} onOpen={onOpenSource} />
      </Panel>

      <ChecksPanel checks={detail.checks} />

      <div className={styles.actions}>
        {pending.waiting ? (
          <p role="status" className={styles.undo}>
            <strong>{pending.label}.</strong> {words.actions.undoIn(pending.secondsLeft ?? 0)}{" "}
            <button type="button" className={styles.linkButton} onClick={pending.undo}>
              {actions.undo}
            </button>
          </p>
        ) : null}
        {pending.saving ? <p role="status">{words.actions.saving}</p> : null}
        {decisions.error ? <ErrorNote error={decisions.error} lead={words.actions.failed} /> : null}

        <div className={styles.buttons}>
          <button type="button" className={styles.primary} onClick={approve} disabled={locked}>
            {approveLabel.button}
          </button>
          <button
            type="button"
            className={styles.secondary}
            onClick={() => open("reject")}
            disabled={locked}
            aria-expanded={panel === "reject"}
          >
            {actions.reject.button}
          </button>
          <button
            type="button"
            className={styles.secondary}
            onClick={() => open("escalate")}
            disabled={locked}
            aria-expanded={panel === "escalate"}
          >
            {actions.escalate.button}
          </button>
        </div>

        {panel === "reject" ? (
          <InlineForm
            label={words.actions.reasonLabel}
            value={reason}
            onChange={setReason}
            onSubmit={reject}
            onCancel={() => setPanel(null)}
            submitLabel={words.actions.send}
            cancelLabel={words.actions.cancel}
            required
            invalid={missing && reason.trim() === ""}
            invalidMessage={words.actions.reasonRequired}
          />
        ) : null}
        {panel === "escalate" ? (
          <InlineForm
            label={words.actions.noteLabel}
            value={note}
            onChange={setNote}
            onSubmit={() => void escalate()}
            onCancel={() => setPanel(null)}
            submitLabel={words.actions.sendEscalate}
            cancelLabel={words.actions.cancel}
            required
            invalid={missing && note.trim() === ""}
            invalidMessage={words.actions.noteRequired}
            busy={decisions.busy === "escalate"}
          />
        ) : null}
      </div>
    </>
  );
}
