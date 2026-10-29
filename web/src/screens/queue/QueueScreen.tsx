import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ErrorPanel } from "../../components/ErrorPanel";
import { useStatus } from "../../components/StatusProvider";
import { queue as words } from "../../copy";
import { useDebounced } from "../../hooks/useDebounced";
import { useNow } from "../../hooks/useNow";
import { shortcutKey } from "../../hooks/shortcuts";
import { QueueRow, QueueRowPlaceholder } from "./QueueRow";
import { currentTab, FILTERS, parseView, viewToSearch, type Filter } from "./params";
import { useQueue } from "./useQueue";
import styles from "./Queue.module.css";

const SEARCH_DELAY_MS = 300;
const PLACEHOLDER_ROWS = 6;

/** j and k move focus through the rows; Enter on a focused row opens it. */
function useRowKeys(list: React.RefObject<HTMLUListElement | null>) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const key = shortcutKey(event);
      if (key !== "j" && key !== "k") return;
      const rows = Array.from(list.current?.querySelectorAll<HTMLElement>("a[data-row]") ?? []);
      if (rows.length === 0) return;
      const at = rows.indexOf(document.activeElement as HTMLElement);
      const next = key === "j" ? (at < 0 ? 0 : at + 1) : at < 0 ? rows.length - 1 : at - 1;
      rows[Math.min(Math.max(next, 0), rows.length - 1)]?.focus();
      event.preventDefault();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [list]);
}

export function QueueScreen() {
  const [params, setParams] = useSearchParams();
  const [text, setText] = useState("");
  const q = useDebounced(text, SEARCH_DELAY_MS);
  const view = parseView(params, q);
  const queue = useQueue(view);
  const { data: status } = useStatus();
  const list = useRef<HTMLUListElement>(null);
  useRowKeys(list);

  const tab = currentTab(view);
  const counts: Partial<Record<Filter, number>> = status
    ? {
        review: status.attention.needs_review,
        escalated: status.attention.escalated,
        failed: status.attention.failed,
      }
    : {};
  const narrowed = view.urgentOnly || view.q !== "";

  const showAll = () => {
    setText("");
    setParams(viewToSearch({ filter: "all", urgentOnly: false }), { replace: false });
  };
  const clearUrgent = () => setParams(viewToSearch({ filter: view.filter, urgentOnly: false }));
  const onSearch = (event: FormEvent) => event.preventDefault();
  const now = useNow();

  let body;
  if (queue.loading) {
    body = (
      <div aria-busy="true">
        <p role="status" className="visually-hidden">
          {words.loading}
        </p>
        <ul className={styles.list}>
          {Array.from({ length: PLACEHOLDER_ROWS }, (_, n) => (
            <QueueRowPlaceholder key={n} />
          ))}
        </ul>
      </div>
    );
  } else if (!queue.hasData) {
    body = <ErrorPanel error={queue.error} onRetry={queue.reload} />;
  } else if (queue.items.length === 0) {
    body = narrowed ? (
      <div className={styles.message}>
        <p>{words.noResults}</p>
        <button type="button" className={styles.button} onClick={showAll}>
          {words.showAll}
        </button>
      </div>
    ) : (
      <div className={styles.message}>
        <p>{tab === "archived" ? words.emptyArchived : words.empty}</p>
      </div>
    );
  } else {
    body = (
      <>
        <ul className={styles.list} ref={list} aria-label={words.listLabel}>
          {queue.items.map((item) => (
            <QueueRow key={item.id} item={item} now={now} />
          ))}
        </ul>
        {queue.hasMore ? (
          <div className={styles.more}>
            <button
              type="button"
              className={styles.button}
              onClick={() => void queue.loadMore()}
              disabled={queue.loadingMore}
            >
              {queue.loadingMore ? words.loadingMore : words.showMore}
            </button>
            {queue.moreFailed ? <p role="status">{words.moreFailed}</p> : null}
          </div>
        ) : null}
      </>
    );
  }

  return (
    <section aria-labelledby="page-title">
      <h1 id="page-title">{words.title}</h1>

      <div className={styles.controls}>
        <nav aria-label={words.filtersLabel} className={styles.tabs}>
          {FILTERS.map((filter) => (
            <Link
              key={filter}
              to={`/${viewToSearch({ filter, urgentOnly: view.urgentOnly })}`}
              className={styles.tab}
              aria-current={tab === filter ? "page" : undefined}
            >
              {words.tabs[filter]}
              {counts[filter] !== undefined ? (
                <>
                  {" "}
                  <span className={styles.count}>{counts[filter]}</span>
                </>
              ) : null}
            </Link>
          ))}
        </nav>
        <form role="search" onSubmit={onSearch} className={styles.search}>
          <label htmlFor="queue-search">{words.searchLabel}</label>
          <input
            id="queue-search"
            type="search"
            maxLength={200}
            value={text}
            onChange={(event) => setText(event.target.value)}
            aria-describedby="queue-search-hint"
          />
          <span id="queue-search-hint" className="visually-hidden">
            {words.searchHint}
          </span>
        </form>
      </div>

      {view.urgentOnly ? (
        <p className={styles.pill}>
          <span>{words.urgentOnly}</span>
          <button type="button" className={styles.linkButton} onClick={clearUrgent}>
            {words.urgentOnlyClear}
          </button>
        </p>
      ) : null}

      {body}
    </section>
  );
}
