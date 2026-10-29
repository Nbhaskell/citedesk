import { useId, useState, type ReactNode } from "react";
import { useApi } from "../../api/context";
import type { ApiError } from "../../api/client";
import type { SettingsView, StatusResponse } from "../../api/types";
import { ErrorPanel } from "../../components/ErrorPanel";
import { useAnnounce } from "../../components/LiveRegion";
import { useStatus } from "../../components/StatusProvider";
import { errors, reason, settings as words } from "../../copy";
import { setShortcutsEnabled, shortcutsEnabled } from "../../hooks/shortcuts";
import { useNow } from "../../hooks/useNow";
import { useResource } from "../../hooks/useResource";
import { ageText } from "../../lib/age";
import styles from "./Settings.module.css";

type Known = "ok" | "error" | "not_checked";

/** A state in words and a symbol. The symbol is decoration: the word says the same thing. */
function State({
  known,
  ok,
  bad,
  unknown,
}: {
  known: Known;
  ok: string;
  bad: string;
  unknown: string;
}) {
  if (known === "ok") {
    return (
      <strong className={styles.ok}>
        <span aria-hidden="true">✓ </span>
        {ok}
      </strong>
    );
  }
  if (known === "error") {
    return (
      <strong className={styles.bad}>
        <span aria-hidden="true">✕ </span>
        {bad}
      </strong>
    );
  }
  return (
    <strong className={styles.unknown}>
      <span aria-hidden="true">– </span>
      {unknown}
    </strong>
  );
}

function Service({ label, children }: { label: string; children: ReactNode }) {
  return (
    <li className={styles.service}>
      <span className={styles.serviceName}>{label}</span>
      {children}
    </li>
  );
}

/** The status as last asked for: from a "Check again" if that is newer than the last poll. */
function newest(polled: StatusResponse | null, asked: StatusResponse | null) {
  if (!asked) return polled;
  if (!polled?.checked_at || (asked.checked_at ?? "") >= polled.checked_at) return asked;
  return polled;
}

function Services({ model }: { model: string }) {
  const api = useApi();
  const announce = useAnnounce();
  const polled = useStatus();
  const now = useNow();
  const [asked, setAsked] = useState<StatusResponse | null>(null);
  const [checking, setChecking] = useState(false);
  const [failure, setFailure] = useState<ApiError | Error | null>(null);
  const status = newest(polled.data, asked);

  const check = async () => {
    setChecking(true);
    setFailure(null);
    try {
      setAsked(await api.checkStatus());
      polled.reload();
      announce(words.services.checkDone);
    } catch (caught) {
      setFailure(caught instanceof Error ? caught : new Error("failed"));
    } finally {
      setChecking(false);
    }
  };

  const modelState = status?.components.model;
  const documentsState = status?.components.knowledge_base;
  const detail = (part: typeof modelState, service: "model" | "documents") => {
    if (!part || part.status === "not_checked") return words.services.notCheckedHint(service);
    return part.status === "error" ? words.services.reason(part.reason) : null;
  };

  return (
    <section className={styles.block}>
      <h2>{words.services.title}</h2>
      {polled.error ? <p className={styles.caution}>{words.services.stale}</p> : null}
      <ul className={styles.services}>
        <Service label={words.services.model(model)}>
          <State
            known={modelState?.status ?? "not_checked"}
            ok={words.services.ok}
            bad={words.services.error}
            unknown={words.services.notChecked}
          />
          <p className={styles.detail}>{detail(modelState, "model")}</p>
        </Service>
        <Service label={words.services.documents}>
          <State
            known={documentsState?.status ?? "not_checked"}
            ok={words.services.ok}
            bad={words.services.error}
            unknown={words.services.notChecked}
          />
          <p className={styles.detail}>{detail(documentsState, "documents")}</p>
        </Service>
        <Service label={words.services.database}>
          <State
            known={status ? status.components.database.status : "not_checked"}
            ok={words.services.ok}
            bad={words.services.error}
            unknown={words.services.notChecked}
          />
        </Service>
        <Service label={words.services.worker}>
          <State
            known={status ? (status.worker_running ? "ok" : "error") : "not_checked"}
            ok={words.services.running}
            bad={words.services.stopped}
            unknown={words.services.notChecked}
          />
        </Service>
      </ul>
      <div className={styles.checkRow}>
        <button
          type="button"
          className={styles.button}
          onClick={() => void check()}
          disabled={checking}
        >
          {checking ? words.services.checking : words.services.checkAgain}
        </button>
        {status?.checked_at ? (
          <span className={styles.sample}>
            {words.services.checkedAt(ageText(status.checked_at, now))}
          </span>
        ) : null}
      </div>
      {failure ? (
        <p role="alert" className={styles.problem}>
          {words.services.checkFailed}{" "}
          {"unreachable" in failure && !failure.unreachable ? failure.message : errors.unreachable}
        </p>
      ) : null}
    </section>
  );
}

function Rules({ rules }: { rules: SettingsView["rules"] }) {
  const id = useId();
  return (
    <section className={styles.block}>
      <h2 id={id}>{words.rules.title}</h2>
      <p>{words.rules.note}</p>
      <table aria-labelledby={id} className={styles.table}>
        <thead>
          <tr>
            <th scope="col">{words.rules.colRule}</th>
            <th scope="col">{words.rules.colState}</th>
            <th scope="col">{words.rules.colSetBy}</th>
          </tr>
        </thead>
        <tbody>
          {rules.map((rule) => (
            <tr key={rule.code}>
              <th scope="row">{reason[rule.code]}</th>
              <td>
                <State
                  known={rule.enabled ? "ok" : "error"}
                  ok={words.rules.on}
                  bad={words.rules.off}
                  unknown=""
                />
              </td>
              <td>{rule.set_by === "environment" ? words.rules.environment : words.rules.code}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

/** The one setting that can be changed here. It lives in this browser only (WCAG 2.1.4). */
function Shortcuts() {
  const id = useId();
  const hintId = useId();
  const [on, setOn] = useState(shortcutsEnabled);
  const [kept, setKept] = useState(true);
  return (
    <section className={styles.block}>
      <h2>{words.browser.title}</h2>
      <div className={styles.switch}>
        <input
          id={id}
          type="checkbox"
          checked={on}
          aria-describedby={hintId}
          onChange={(event) => {
            const next = event.target.checked;
            setOn(next);
            setShortcutsEnabled(next);
            setKept(shortcutsEnabled() === next);
          }}
        />
        <label htmlFor={id}>{words.browser.shortcuts}</label>
      </div>
      <p id={hintId} className={styles.sample}>
        {words.browser.shortcutsHint}
      </p>
      {kept ? null : <p className={styles.problem}>{words.browser.notSaved}</p>}
    </section>
  );
}

function Facts({ data }: { data: SettingsView }) {
  const business = data.business;
  return (
    <>
      <section className={styles.block}>
        <h2>{words.business.title}</h2>
        {business ? (
          <dl className={styles.facts}>
            <dt>{words.business.name}</dt>
            <dd>{business.name}</dd>
            <dt>{words.business.phone}</dt>
            <dd>{business.phone}</dd>
            <dt>{words.business.emergencyPhone}</dt>
            <dd>{business.emergency_phone}</dd>
            <dt>{words.business.email}</dt>
            <dd>{business.email}</dd>
          </dl>
        ) : (
          <p className={styles.problem}>{words.business.missing}</p>
        )}
      </section>

      <section className={styles.block}>
        <h2>{words.replies.title}</h2>
        <p>{words.replies.limit(data.draft_max_words)}</p>
        <p>{words.replies.neverSent}</p>
      </section>

      <Services model={data.model} />
      <Rules rules={data.rules} />

      <section className={styles.block}>
        <h2>{words.data.title}</h2>
        <p>{data.synthetic_data ? words.data.synthetic : words.data.real}</p>
      </section>

      <Shortcuts />
    </>
  );
}

export function SettingsScreen() {
  const api = useApi();
  const { data, error, loading, reload } = useResource((signal) => api.settings(signal));

  let body;
  if (loading) {
    body = (
      <div aria-busy="true">
        <p role="status" className="visually-hidden">
          {words.loading}
        </p>
        <div aria-hidden="true">
          {[0, 1, 2].map((n) => (
            <span key={n} className={styles.placeholder} style={{ width: `${70 - n * 15}%` }} />
          ))}
        </div>
      </div>
    );
  } else if (!data) {
    body = <ErrorPanel error={error} onRetry={reload} />;
  } else {
    body = <Facts data={data} />;
  }

  return (
    <section aria-labelledby="page-title">
      <h1 id="page-title">{words.title}</h1>
      <p className={styles.intro}>{words.intro}</p>
      {body}
    </section>
  );
}
