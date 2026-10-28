import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { useApi } from "../../api/context";
import type { InquiryDetail } from "../../api/types";
import { useAnnounce } from "../../components/LiveRegion";
import { actions, app, detail as words, errors, processingWords, reasonWords } from "../../copy";
import { useResource } from "../../hooks/useResource";
import { blockedNotice } from "./checks";
import { DraftView } from "./draft";
import { ErrorNote, InlineForm } from "./forms";
import { ChecksPanel, Panel } from "./parts";
import { stageLabel } from "./stages";
import type { Decisions } from "./useDecisions";
import styles from "./Detail.module.css";

type Props = { detail: InquiryDetail; decisions: Decisions };

function Banner({
  title,
  children,
  tone,
}: {
  title: string;
  children: ReactNode;
  tone: "stop" | "info";
}) {
  return (
    <section className={`${styles.banner} ${styles[`banner_${tone}`]}`}>
      <h2>{title}</h2>
      {children}
    </section>
  );
}

function Reasons({ detail }: { detail: InquiryDetail }) {
  const open = detail.escalations.filter((e) => !e.resolved);
  if (open.length === 0) return null;
  return (
    <ul>
      {open.map((e) => (
        <li key={e.id}>{reasonWords(e.reason_code, e.source)}</li>
      ))}
    </ul>
  );
}

/** "Mark resolved", with a note if the person wants to leave one. */
function ResolveForm({ detail, decisions }: Props) {
  const [note, setNote] = useState("");
  return (
    <>
      {decisions.error ? <ErrorNote error={decisions.error} /> : null}
      <InlineForm
        label={words.actions.resolveNote}
        value={note}
        onChange={setNote}
        onSubmit={() => void decisions.resolve(detail.inquiry.id, note.trim() || undefined)}
        submitLabel={actions.resolve.button}
        required={false}
        invalid={false}
        invalidMessage=""
        busy={decisions.busy === "resolve"}
      />
    </>
  );
}

/** A draft kept for reference only, folded away and labelled as not checked for sending. */
function ReferenceDraft({ detail }: { detail: InquiryDetail }) {
  if (!detail.draft) return null;
  return (
    <details className={styles.reference}>
      <summary>{words.draft.forReference}</summary>
      <DraftView draft={detail.draft} checks={detail.checks} />
    </details>
  );
}

export function ProcessingPanel({ detail }: Props) {
  return (
    <Banner title={words.processing.title} tone="info">
      <p role="status" className={styles.stage}>
        {processingWords(detail.inquiry.status, detail.retrievals.length > 0)}…
      </p>
      <p>{words.processing.body}</p>
    </Banner>
  );
}

export function FailedPanel({ detail, decisions }: Props) {
  const stage = detail.inquiry.failure_stage;
  return (
    <Banner title={words.failed.title} tone="stop">
      {stage ? <p>{words.failed.at(stageLabel(stage))}</p> : null}
      {detail.inquiry.failure_message ? <p>{detail.inquiry.failure_message}</p> : null}
      <p>{words.failed.retryHint}</p>
      {decisions.error ? <ErrorNote error={decisions.error} /> : null}
      <div className={styles.buttons}>
        <button
          type="button"
          className={styles.primary}
          disabled={decisions.busy !== null}
          onClick={() => void decisions.retry(detail.inquiry.id, stage ?? "")}
        >
          {actions.retry.button}
        </button>
      </div>
    </Banner>
  );
}

export function EscalatedPanel({ detail, decisions }: Props) {
  return (
    <>
      <Banner title={words.escalated.title} tone="stop">
        <p>{words.escalated.body}</p>
        <Reasons detail={detail} />
      </Banner>
      <ReferenceDraft detail={detail} />
      <p>{words.escalated.resolveHint}</p>
      <ResolveForm detail={detail} decisions={decisions} />
    </>
  );
}

export function BlockedPanel({ detail, decisions }: Props) {
  const notice = blockedNotice(detail.checks);
  return (
    <>
      <Banner title={words.blocked.title} tone="stop">
        {notice ? <p className={styles.notice}>{notice}</p> : null}
        <p>{words.blocked.body}</p>
        <Reasons detail={detail} />
      </Banner>
      {detail.draft ? (
        <Panel title={words.sections.draft}>
          <DraftView draft={detail.draft} checks={detail.checks} />
        </Panel>
      ) : null}
      <ChecksPanel checks={detail.checks} />
      <ResolveForm detail={detail} decisions={decisions} />
    </>
  );
}

export function RefusalPanel({ detail, decisions }: Props) {
  return (
    <>
      <Banner title={words.refusal.title} tone="stop">
        <p>{words.refusal.body}</p>
      </Banner>
      {detail.draft ? (
        <details className={styles.reference}>
          <summary>{words.draft.forReference}</summary>
          <p className={styles.meta}>{words.refusal.holding}</p>
          <DraftView draft={detail.draft} checks={[]} />
        </details>
      ) : null}
      <ResolveForm detail={detail} decisions={decisions} />
    </>
  );
}

export function RejectedPanel({ detail, decisions }: Props) {
  const draft = detail.draft;
  const [guidance, setGuidance] = useState("");
  const [missing, setMissing] = useState(false);
  const writing = decisions.busy === "redraft";

  const redraft = async () => {
    if (!draft) return;
    if (guidance.trim() === "") {
      setMissing(true);
      return;
    }
    setMissing(false);
    if (await decisions.redraft(draft.id, guidance.trim())) setGuidance("");
  };

  return (
    <>
      <Banner title={words.rejected.title} tone="info">
        <p>{words.rejected.body}</p>
      </Banner>
      <ReferenceDraft detail={detail} />
      {decisions.error ? <ErrorNote error={decisions.error} /> : null}
      {writing ? (
        <p role="status" className={styles.stage}>
          {words.rejected.writing}
        </p>
      ) : null}
      {draft ? (
        <InlineForm
          label={words.rejected.guidanceLabel}
          value={guidance}
          onChange={setGuidance}
          onSubmit={() => void redraft()}
          submitLabel={words.rejected.redraft}
          required
          invalid={missing && guidance.trim() === ""}
          invalidMessage={words.rejected.guidanceRequired}
          busy={decisions.busy !== null}
        />
      ) : null}
      <div className={styles.buttons}>
        <button
          type="button"
          className={styles.secondary}
          disabled={decisions.busy !== null}
          onClick={() => void decisions.resolve(detail.inquiry.id, undefined)}
        >
          {words.rejected.close}
        </button>
      </div>
    </>
  );
}

/** The approved text, with the one button that matters: copy it. Nothing here sends anything. */
export function ApprovedPanel({
  detail,
  copied,
  apply,
}: {
  detail: InquiryDetail;
  copied: boolean;
  apply: (detail: InquiryDetail) => void;
}) {
  const api = useApi();
  const announce = useAnnounce();
  const draftId = detail.draft?.id ?? 0;
  const text = useResource((signal) => api.exportText(draftId, signal), { key: String(draftId) });
  const [copyError, setCopyError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<Error | null>(null);

  const copy = async () => {
    if (!text.data) return;
    setCopyError(null);
    setFailure(null);
    setBusy(true);
    try {
      try {
        await navigator.clipboard.writeText(text.data.body);
      } catch {
        setCopyError(words.approved.copyFailed);
        return;
      }
      await api.recordExport(draftId);
      apply(await api.inquiry(detail.inquiry.id));
      announce(actions.copy.done);
    } catch (caught) {
      setFailure(caught instanceof Error ? caught : new Error("failed"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <Banner title={copied ? words.approved.copiedTitle : words.approved.title} tone="info">
        <p>{copied ? words.closed.exported : words.approved.hint}</p>
      </Banner>
      <Panel title={words.sections.draft}>
        {text.error && !text.data ? (
          <p role="alert">{errors.unreachable}</p>
        ) : text.data ? (
          <>
            {text.data.subject ? (
              <p>
                <span className={styles.label}>{words.approved.subject}</span>{" "}
                <span className={styles.subject}>{text.data.subject}</span>
              </p>
            ) : null}
            <p className={styles.prose}>{text.data.body}</p>
          </>
        ) : (
          <p className={styles.faint}>{words.loading}</p>
        )}
        {copyError ? (
          <p role="alert" className={styles.errorNote}>
            {copyError}
          </p>
        ) : null}
        {failure ? (
          <p role="alert" className={styles.errorNote}>
            {errors.unreachable}
          </p>
        ) : null}
        <div className={styles.buttons}>
          <button
            type="button"
            className={styles.primary}
            onClick={() => void copy()}
            disabled={busy || !text.data}
          >
            {copied ? "Copy again" : actions.copy.button}
          </button>
        </div>
        <p className={styles.meta}>{app.nothingSent}</p>
      </Panel>
    </>
  );
}

export function ClosedPanel({ detail }: { detail: InquiryDetail }) {
  const status = detail.inquiry.status;
  return (
    <>
      <Banner title={words.sections.draft} tone="info">
        <p>
          {status === "resolved" ? words.closed.resolved : null}
          {status === "archived" ? words.closed.archived : null}
        </p>
      </Banner>
      <ReferenceDraft detail={detail} />
      <p>
        <Link to="/">{errors.backToQueue}</Link>
      </p>
    </>
  );
}
