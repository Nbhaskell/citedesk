import { useId, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import type {
  Classification,
  DraftCheck,
  Escalation,
  Extraction,
  InquiryDetail,
  Source,
} from "../../api/types";
import { UrgencyTag } from "../../components/UrgencyTag";
import {
  confidence,
  detail as words,
  fieldLabel,
  intent,
  missingField,
  property,
  reasonWords,
  route,
  sentiment,
  service,
} from "../../copy";
import { useNow } from "../../hooks/useNow";
import { ageText, exactText } from "../../lib/age";
import { describeChecks, groundedFigures } from "./checks";
import { historyLines } from "./history";
import { highlight, type Segment } from "./sources";
import styles from "./Detail.module.css";

/** Text with some pieces marked. Always rendered as text: a `<mark>` around a string, never HTML. */
export function Marked({ segments }: { segments: Segment[] }) {
  return (
    <>
      {segments.map((segment, n) =>
        segment.marked ? <mark key={n}>{segment.text}</mark> : <span key={n}>{segment.text}</span>,
      )}
    </>
  );
}

export function Panel({
  title,
  id,
  children,
}: {
  title: string;
  id?: string;
  children: ReactNode;
}) {
  const heading = useId();
  return (
    <section className={styles.panel} aria-labelledby={heading} id={id}>
      <h2 id={heading}>{title}</h2>
      {children}
    </section>
  );
}

// --- the customer's message -------------------------------------------------------------------

export function OriginalMessage({ detail }: { detail: InquiryDetail }) {
  const { inquiry, screening, duplicates } = detail;
  const now = useNow();
  return (
    <Panel title={words.sections.message} id="original-message">
      <p className={styles.meta}>
        {words.message.from} {inquiry.sender_name ?? "an unknown sender"}
        {inquiry.sender_email ? ` (${inquiry.sender_email})` : ""}
        {" · "}
        <time dateTime={inquiry.received_at} title={exactText(inquiry.received_at)}>
          {ageText(inquiry.received_at, now)}
        </time>
      </p>
      {screening?.sensitive_data_masked ? (
        <p className={styles.warning} role="note">
          {words.message.masked}
        </p>
      ) : null}
      {screening?.result === "injection_suspected" ? (
        <p className={styles.warning} role="note">
          {words.message.injection}
        </p>
      ) : null}
      {inquiry.subject ? <p className={styles.subject}>{inquiry.subject}</p> : null}
      <p className={styles.prose}>{inquiry.body}</p>
      {inquiry.duplicate_of !== null ? (
        <p className={styles.meta}>
          {words.message.repeatOf}{" "}
          <Link to={`/inquiries/${inquiry.duplicate_of}`}>#{inquiry.duplicate_of}</Link>
        </p>
      ) : null}
      {duplicates.length > 0 ? (
        <p className={styles.meta}>
          {words.message.alsoSent}{" "}
          {duplicates.map((id, n) => (
            <span key={id}>
              {n > 0 ? ", " : ""}
              <Link to={`/inquiries/${id}`}>#{id}</Link>
            </span>
          ))}
        </p>
      ) : null}
    </Panel>
  );
}

// --- what the system understood ---------------------------------------------------------------

function wants(classification: Classification): string[] {
  const primary = classification.intents.find((i) => i.intent === classification.primary_intent);
  const rest = classification.intents.filter((i) => i !== primary);
  return [...(primary ? [primary] : []), ...rest].map((i) =>
    i.confidence === "high"
      ? intent[i.intent]
      : `${intent[i.intent]} (${confidence[i.confidence]})`,
  );
}

function fieldValue(extraction: Extraction, name: keyof Extraction["fields"]): string | null {
  const value = extraction.fields[name];
  if (value === null || value === undefined || value === "") return null;
  if (name === "service_type") return service[extraction.fields.service_type ?? "unknown"];
  if (name === "property_type") return property[extraction.fields.property_type ?? "unknown"];
  return String(value);
}

const FIELD_ORDER: (keyof Extraction["fields"])[] = [
  "service_type",
  "start_date",
  "dates_as_written",
  "property_type",
  "address_area",
  "preferred_contact",
  "booking_reference",
];

export function UnderstoodAs({ detail }: { detail: InquiryDetail }) {
  const { classification, extraction, inquiry, escalations, screening } = detail;
  const open: Escalation[] = escalations.filter((e) => !e.resolved);
  return (
    <Panel title={words.sections.understood}>
      {classification ? (
        <>
          {classification.summary ? (
            <p className={styles.summaryText}>{classification.summary}</p>
          ) : null}
          <dl className={styles.facts}>
            <dt>{words.understood.wants}</dt>
            <dd>{wants(classification).join(", ")}</dd>
            <dt>{words.understood.urgency}</dt>
            <dd>
              <UrgencyTag urgency={classification.urgency} />
            </dd>
            <dt>{words.understood.tone}</dt>
            <dd>{sentiment[classification.sentiment]}</dd>
          </dl>
        </>
      ) : (
        <p>
          {words.understood.notRead}
          {screening?.result === "injection_suspected"
            ? ` ${words.understood.notReadInjection}`
            : ""}
        </p>
      )}
      {extraction ? (
        <>
          <h3>{words.understood.found}</h3>
          <dl className={styles.facts}>
            {FIELD_ORDER.map((name) => {
              const value = fieldValue(extraction, name);
              return (
                <div key={name} className={styles.fact}>
                  <dt>{fieldLabel[name]}</dt>
                  <dd className={value === null ? styles.faint : undefined}>
                    {value ?? words.understood.notStated}
                  </dd>
                </div>
              );
            })}
          </dl>
          {extraction.missing_fields.length > 0 ? (
            <div className={styles.missing}>
              <h3>{words.understood.missing}</h3>
              <ul>
                {extraction.missing_fields.map((name) => (
                  <li key={name}>{missingField[name] ?? name.replace(/_/g, " ")}</li>
                ))}
              </ul>
            </div>
          ) : null}
        </>
      ) : null}
      <h3>{words.understood.route}</h3>
      <p>{inquiry.route ? route[inquiry.route] : "Not decided yet"}</p>
      {open.length > 0 ? (
        <>
          <h3>{words.understood.reasons}</h3>
          <ul>
            {open.map((e) => (
              <li key={e.id}>
                {reasonWords(e.reason_code, e.source)}
                {e.detail ? <span className={styles.faint}> — {e.detail}</span> : null}
              </li>
            ))}
          </ul>
        </>
      ) : null}
    </Panel>
  );
}

// --- checks -----------------------------------------------------------------------------------

export function ChecksPanel({ checks }: { checks: DraftCheck[] }) {
  const views = describeChecks(checks);
  return (
    <Panel title={words.sections.checks}>
      {views.length === 0 ? (
        <p className={styles.faint}>{words.checks.none}</p>
      ) : (
        <ul className={styles.checks}>
          {views.map((view) => {
            const state = view.passed ? "passed" : view.blocking ? "failed" : "warning";
            return (
              <li key={view.code} className={styles[`check_${state}`]}>
                <span className={styles.checkState}>
                  <span aria-hidden="true">{view.passed ? "✓" : view.blocking ? "✕" : "!"}</span>{" "}
                  {words.checks[state]}
                </span>
                <span className={styles.checkTitle}>{view.title}</span>
                {view.lines.map((line) => (
                  <span key={line} className={styles.checkLine}>
                    {line}
                  </span>
                ))}
              </li>
            );
          })}
        </ul>
      )}
    </Panel>
  );
}

// --- sources ----------------------------------------------------------------------------------

export function SourcesPanel({
  sources,
  checks,
  open,
  onToggle,
}: {
  sources: Source[];
  checks: DraftCheck[];
  open: ReadonlySet<number>;
  onToggle: (index: number) => void;
}) {
  const grounded = groundedFigures(checks);
  return (
    <Panel title={`${words.sections.sources}${sources.length ? ` (${sources.length})` : ""}`}>
      {sources.length === 0 ? (
        <p className={styles.faint}>{words.sources.none}</p>
      ) : (
        <ol className={styles.sources}>
          {sources.map((source, index) => {
            const expanded = open.has(index);
            return (
              <li key={index} id={`source-${index}`} className={styles.source}>
                <h3>
                  <span aria-hidden="true">[{index}] </span>
                  {source.file} › {source.section}
                  {source.page !== null ? `, ${words.sources.page(source.page)}` : ""}
                </h3>
                <p className={`${styles.prose} ${expanded ? "" : styles.clamped}`}>
                  <Marked segments={highlight(source.text, grounded)} />
                </p>
                <button
                  type="button"
                  className={styles.linkButton}
                  aria-expanded={expanded}
                  onClick={() => onToggle(index)}
                >
                  {expanded ? words.sources.collapse : words.sources.expand}
                  <span className="visually-hidden"> {words.sources.heading(index)}</span>
                </button>
              </li>
            );
          })}
        </ol>
      )}
    </Panel>
  );
}

/** The facts a draft states, each pointing at the passage it came from. */
export function ClaimList({
  claims,
  sourceCount,
  onOpen,
}: {
  claims: { text: string; source_index: number }[];
  sourceCount: number;
  onOpen: (index: number) => void;
}) {
  if (claims.length === 0) return null;
  return (
    <div className={styles.claims}>
      <h3>{words.draft.facts}</h3>
      <ul>
        {claims.map((claim, n) => (
          <li key={n}>
            {claim.text}{" "}
            {claim.source_index < sourceCount ? (
              <button
                type="button"
                className={styles.marker}
                onClick={() => onOpen(claim.source_index)}
                aria-label={words.sources.open(claim.source_index)}
              >
                [{claim.source_index}]
              </button>
            ) : (
              <span className={styles.faint}>(no such passage)</span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

// --- history ----------------------------------------------------------------------------------

export function HistoryPanel({ detail }: { detail: InquiryDetail }) {
  const lines = historyLines(detail.history);
  const now = useNow();
  const [open, setOpen] = useState(false);
  if (lines.length === 0) return null;
  return (
    <details
      className={styles.history}
      open={open}
      onToggle={(event) => setOpen((event.currentTarget as HTMLDetailsElement).open)}
    >
      <summary>
        {words.sections.history} ({lines.length})
      </summary>
      <ul>
        {lines.map((line) => (
          <li key={line.id}>
            {line.text}{" "}
            <time className={styles.faint} dateTime={line.at} title={exactText(line.at)}>
              {ageText(line.at, now)}
            </time>
          </li>
        ))}
      </ul>
    </details>
  );
}
