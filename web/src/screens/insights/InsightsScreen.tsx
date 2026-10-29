import { useId, useState, type ReactNode } from "react";
import { useApi } from "../../api/context";
import type { Insights } from "../../api/types";
import { ErrorPanel } from "../../components/ErrorPanel";
import { decisionWords, insights as words, reason, route } from "../../copy";
import { useResource } from "../../hooks/useResource";
import {
  approvedCount,
  formatDuration,
  formatMinutes,
  loadAssumption,
  MIN_SAMPLE,
  parseMinutes,
  percent,
  periodText,
  saveAssumption,
  savedMinutes,
  type Counted,
} from "./figures";
import styles from "./Insights.module.css";

// The API sends codes as plain strings; a code with no words here is shown as it is.
const wordsFor = (table: Record<string, string>, code: string): string => table[code] ?? code;

/** One figure: its name, the value, and what it is a share or median of. */
function Figure({ label, children }: { label: string; children: ReactNode }) {
  const id = useId();
  return (
    <div role="group" aria-labelledby={id} className={styles.figure}>
      <h3 id={id} className={styles.figureLabel}>
        {label}
      </h3>
      {children}
    </div>
  );
}

function Share({
  label,
  share,
  approved,
}: {
  label: string;
  share: number | null;
  approved: number;
}) {
  return (
    <Figure label={label}>
      {share !== null && approved >= MIN_SAMPLE ? (
        <>
          <p className={styles.value}>{percent(share)}</p>
          <p className={styles.sample}>{words.shareOf(approved)}</p>
        </>
      ) : (
        <p className={styles.sample}>{words.tooFewShare(approved)}</p>
      )}
    </Figure>
  );
}

function Median({
  label,
  seconds,
  sample,
  sampleText,
}: {
  label: string;
  seconds: number | null;
  sample: number;
  sampleText: string;
}) {
  return (
    <Figure label={label}>
      {seconds === null ? (
        <p className={styles.sample}>{words.noTimes}</p>
      ) : (
        <>
          <p className={styles.value}>{formatDuration(seconds)}</p>
          <p className={styles.sample}>{sampleText}</p>
          {sample < MIN_SAMPLE ? <p className={styles.caution}>{words.fewTimes(sample)}</p> : null}
        </>
      )}
    </Figure>
  );
}

/** A table of counts. `share` adds each count's share of all inquiries, with a bar. */
function CountTable({
  title,
  head,
  rows,
  total,
}: {
  title: string;
  head: string;
  rows: Array<Counted & { label: string }>;
  total?: number;
}) {
  const id = useId();
  return (
    <section className={styles.block}>
      <h2 id={id}>{title}</h2>
      <table aria-labelledby={id} className={styles.table}>
        <thead>
          <tr>
            <th scope="col">{words.colWhat}</th>
            <th scope="col" className={styles.number}>
              {head}
            </th>
            {total ? (
              <th scope="col" className={styles.shareCol}>
                {words.colShare}
              </th>
            ) : null}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.code}>
              <th scope="row">{row.label}</th>
              <td className={styles.number}>{row.count}</td>
              {total ? (
                <td className={styles.shareCol}>
                  <span className={styles.bar} aria-hidden="true">
                    <span
                      className={styles.fill}
                      style={{ width: `${Math.min(100, (row.count / total) * 100)}%` }}
                    />
                  </span>
                  {percent(row.count / total)}
                </td>
              ) : null}
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

/** The person's own estimate of time saved. Their number stays in this browser. */
function TimeSaved({ data }: { data: Insights }) {
  const [text, setText] = useState(loadAssumption);
  const inputId = useId();
  const noteId = useId();
  const minutes = parseMinutes(text);
  const invalid = text.trim() !== "" && minutes === null;
  const approved = approvedCount(data.decisions);
  const saved = savedMinutes(approved, minutes, data.median_review_seconds);

  return (
    <section className={styles.block}>
      <h2>{words.saved.title}</h2>
      <div className={styles.field}>
        <label htmlFor={inputId}>{words.saved.label}</label>
        <input
          id={inputId}
          type="text"
          inputMode="decimal"
          autoComplete="off"
          maxLength={8}
          value={text}
          aria-invalid={invalid}
          aria-describedby={noteId}
          onChange={(event) => {
            setText(event.target.value);
            saveAssumption(event.target.value);
          }}
        />
        <p id={noteId} className={styles.sample}>
          {words.saved.hint}
        </p>
      </div>
      {invalid ? (
        <p className={styles.problem}>{words.saved.invalid}</p>
      ) : minutes !== null && saved === null ? (
        <p className={styles.sample}>{words.saved.needsReview}</p>
      ) : minutes !== null && saved !== null && data.median_review_seconds !== null ? (
        <>
          <p className={styles.value}>{words.saved.result(formatMinutes(saved))}</p>
          <p className={styles.sample}>
            {words.saved.basis(
              approved,
              formatMinutes(minutes),
              formatDuration(data.median_review_seconds),
            )}
          </p>
        </>
      ) : null}
    </section>
  );
}

function Figures({ data }: { data: Insights }) {
  const approved = approvedCount(data.decisions);
  const total = data.total_inquiries;
  const reasons = data.escalations_by_reason
    .filter((entry) => entry.count > 0)
    .sort((a, b) => b.count - a.count)
    .map((entry) => ({ ...entry, label: wordsFor(reason, entry.code) }));

  return (
    <>
      <p className={styles.summary}>
        {words.summary(total, periodText(data.period_start, data.period_end))}
      </p>

      <section className={styles.block}>
        <h2>{words.reviews}</h2>
        <div className={styles.figures}>
          <Share
            label={words.asWritten}
            share={data.approved_unchanged_share}
            approved={approved}
          />
          <Share label={words.afterEditing} share={data.edited_share} approved={approved} />
          <Median
            label={words.medianReview}
            seconds={data.median_review_seconds}
            sample={data.review_time_sample}
            sampleText={words.reviewSample(data.review_time_sample)}
          />
          <Median
            label={words.medianDraft}
            seconds={data.median_seconds_to_draft}
            sample={data.draft_time_sample}
            sampleText={words.draftSample(data.draft_time_sample)}
          />
        </div>
      </section>

      <CountTable
        title={words.byRoute}
        head={words.colCount}
        total={total}
        rows={data.by_route.map((entry) => ({
          ...entry,
          label: wordsFor(route, entry.code),
        }))}
      />
      <CountTable
        title={words.byDecision}
        head={words.colDecisions}
        rows={data.decisions.map((entry) => ({
          ...entry,
          label: wordsFor(decisionWords, entry.code),
        }))}
      />
      {reasons.length > 0 ? (
        <CountTable title={words.byReason} head={words.colCount} rows={reasons} />
      ) : (
        <section className={styles.block}>
          <h2>{words.byReason}</h2>
          <p>{words.noReasons}</p>
        </section>
      )}

      <TimeSaved data={data} />
    </>
  );
}

export function InsightsScreen() {
  const api = useApi();
  const { data, error, loading, reload } = useResource((signal) => api.insights(signal));

  let body;
  if (loading) {
    body = (
      <div aria-busy="true">
        <p role="status" className="visually-hidden">
          {words.loading}
        </p>
        <div className={styles.figures} aria-hidden="true">
          {[0, 1, 2, 3].map((n) => (
            <div key={n} className={styles.figure}>
              <span className={styles.placeholder} style={{ width: "60%" }} />
              <span className={styles.placeholder} style={{ width: "40%", height: "2rem" }} />
            </div>
          ))}
        </div>
      </div>
    );
  } else if (!data) {
    body = <ErrorPanel error={error} onRetry={reload} />;
  } else if (data.total_inquiries === 0) {
    body = <p className={styles.empty}>{words.empty}</p>;
  } else {
    body = <Figures data={data} />;
  }

  return (
    <section aria-labelledby="page-title">
      <h1 id="page-title">{words.title}</h1>
      {body}
    </section>
  );
}
