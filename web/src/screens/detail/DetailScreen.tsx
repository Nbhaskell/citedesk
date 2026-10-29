import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { useApi } from "../../api/context";
import { useAnnounce } from "../../components/LiveRegion";
import { UrgencyTag } from "../../components/UrgencyTag";
import { detail as words, errors, stateWords } from "../../copy";
import { modalOpen } from "../../hooks/modal";
import { isTypingTarget, shortcutKey } from "../../hooks/shortcuts";
import { useResource } from "../../hooks/useResource";
import { markViewed } from "../queue/returnFocus";
import { neighbours, readQueueState, type QueueState } from "./neighbours";
import { HistoryPanel, OriginalMessage, SourcesPanel, UnderstoodAs } from "./parts";
import { ReviewPanel } from "./ReviewPanel";
import { mergedSources } from "./sources";
import { useDecisions } from "./useDecisions";
import { useDetail } from "./useDetail";
import { pickVariant } from "./variant";
import {
  ApprovedPanel,
  BlockedPanel,
  ClosedPanel,
  EscalatedPanel,
  FailedPanel,
  ProcessingPanel,
  RefusalPanel,
  RejectedPanel,
} from "./VariantPanels";
import styles from "./Detail.module.css";

const DEFAULT_MAX_WORDS = 200;

function Loading() {
  return (
    <div aria-busy="true">
      <p role="status" className="visually-hidden">
        {words.loading}
      </p>
      <div className={styles.layout} aria-hidden="true">
        {[styles.areaMessage, styles.areaUnderstood, styles.areaPrimary].map((area) => (
          <div key={area} className={`${styles.panel} ${area}`}>
            <span className={styles.bar} style={{ width: "40%" }} />
            <span className={styles.bar} style={{ width: "90%" }} />
            <span className={styles.bar} style={{ width: "70%" }} />
          </div>
        ))}
      </div>
    </div>
  );
}

export function DetailScreen() {
  const params = useParams();
  const id = Number(params["id"]);
  const valid = Number.isInteger(id) && id > 0;
  const api = useApi();
  const navigate = useNavigate();
  const location = useLocation();
  const { detail, loading, error, reload, apply } = useDetail(valid ? id : 0);
  const decisions = useDecisions(apply);
  const settings = useResource((signal) => api.settings(signal), { key: "settings" });
  const [openSources, setOpenSources] = useState<ReadonlySet<number>>(new Set());

  const toggleSource = useCallback((index: number) => {
    setOpenSources((current) => {
      const next = new Set(current);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });
  }, []);
  const openSource = useCallback((index: number) => {
    setOpenSources((current) => new Set(current).add(index));
    // After the passage is shown, bring it into view and say where focus went.
    requestAnimationFrame(() =>
      document.getElementById(`source-${index}`)?.scrollIntoView?.({ block: "nearest" }),
    );
  }, []);

  // The queue row to come back to, and the list this inquiry was opened from (for j and k).
  useEffect(() => {
    if (valid) markViewed(id);
  }, [valid, id]);
  const queueIds = readQueueState(location.state);
  const ring = valid ? neighbours(queueIds, id) : null;
  const ringState: QueueState = { queue: queueIds };

  // Escape goes back to where the person came from, unless something else used the key first
  // (an open form, a decision waiting to be undone or the shortcut list claim it first).
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.defaultPrevented || event.key !== "Escape" || isTypingTarget(event.target)) return;
      if (modalOpen()) return;
      if (location.key !== "default") navigate(-1);
      else navigate("/");
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [navigate, location.key]);

  // j and k: the next and previous inquiry in the list this one was opened from. The move
  // replaces this page in the history, so Escape still goes back to the queue in one step.
  const next = ring?.next ?? null;
  const previous = ring?.previous ?? null;
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const key = shortcutKey(event);
      const target = key === "j" ? next : key === "k" ? previous : null;
      if (target === null) return;
      event.preventDefault();
      const state: QueueState = { queue: queueIds };
      navigate(`/inquiries/${target}`, { replace: true, state });
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [navigate, next, previous, queueIds]);

  // Say where a move landed, since the page changes under a screen reader.
  const announce = useAnnounce();
  const lastId = useRef(id);
  useEffect(() => {
    if (lastId.current !== id && ring) announce(words.ring.moved(id, ring.position, ring.total));
    lastId.current = id;
  }, [id, ring, announce]);

  if (!valid || (error?.httpStatus === 404 && !detail)) {
    return (
      <section aria-labelledby="page-title">
        <h1 id="page-title">{words.title}</h1>
        <p>{words.notFound}</p>
        <p>
          <Link to="/">{errors.backToQueue}</Link>
        </p>
      </section>
    );
  }

  const header = (
    <>
      <div className={styles.crumbs}>
        <Link to="/">{words.back}</Link>
        {ring ? (
          <nav aria-label={words.ring.label} className={styles.ring}>
            <span>{words.ring.position(ring.position, ring.total)}</span>
            {ring.previous !== null ? (
              <Link
                to={`/inquiries/${ring.previous}`}
                state={ringState}
                replace
                aria-keyshortcuts="k"
              >
                {words.ring.previous}
              </Link>
            ) : null}
            {ring.next !== null ? (
              <Link to={`/inquiries/${ring.next}`} state={ringState} replace aria-keyshortcuts="j">
                {words.ring.next}
              </Link>
            ) : null}
          </nav>
        ) : null}
      </div>
      <h1 id="page-title">
        {words.title} {id}
      </h1>
    </>
  );

  if (!detail) {
    return (
      <section aria-labelledby="page-title">
        {header}
        {loading ? (
          <Loading />
        ) : (
          <div className={styles.banner}>
            <p>
              {error?.unreachable ? errors.unreachable : (error?.message ?? errors.unreachable)}
            </p>
            {error?.requestId ? (
              <p className={styles.meta}>
                {errors.requestId} {error.requestId}
              </p>
            ) : null}
            <button type="button" className={styles.secondary} onClick={reload}>
              {errors.retry}
            </button>
          </div>
        )}
      </section>
    );
  }

  const variant = pickVariant(detail);
  const sources = mergedSources(detail.retrievals);
  const maxWords = settings.data?.draft_max_words ?? DEFAULT_MAX_WORDS;
  const showSources = variant !== "processing" && variant !== "failed";

  let primary;
  switch (variant) {
    case "processing":
      primary = <ProcessingPanel detail={detail} decisions={decisions} />;
      break;
    case "failed":
      primary = <FailedPanel detail={detail} decisions={decisions} />;
      break;
    case "blocked":
      primary = <BlockedPanel detail={detail} decisions={decisions} />;
      break;
    case "refusal":
      primary = <RefusalPanel detail={detail} decisions={decisions} />;
      break;
    case "escalated":
      primary = <EscalatedPanel detail={detail} decisions={decisions} />;
      break;
    case "review":
      primary = (
        <ReviewPanel
          detail={detail}
          decisions={decisions}
          maxWords={maxWords}
          sources={sources}
          onOpenSource={openSource}
        />
      );
      break;
    case "rejected":
      primary = <RejectedPanel detail={detail} decisions={decisions} />;
      break;
    case "approved":
      primary = <ApprovedPanel detail={detail} copied={false} apply={apply} />;
      break;
    case "closed":
      primary =
        detail.inquiry.status === "exported" ? (
          <ApprovedPanel detail={detail} copied apply={apply} />
        ) : (
          <ClosedPanel detail={detail} />
        );
      break;
  }

  return (
    <section aria-labelledby="page-title">
      {header}
      <p className={styles.stateLine}>
        {detail.inquiry.urgency ? <UrgencyTag urgency={detail.inquiry.urgency} /> : null}{" "}
        <span>{stateWords(detail.inquiry.status, detail.inquiry.route)}</span>
        <a href="#original-message" className={styles.jump}>
          {words.jumpToMessage}
        </a>
      </p>
      <div className={styles.layout}>
        <div className={styles.areaUnderstood}>
          <UnderstoodAs detail={detail} />
        </div>
        <div className={styles.areaPrimary}>{primary}</div>
        {showSources ? (
          <div className={styles.areaSources}>
            <SourcesPanel
              sources={sources}
              checks={detail.checks}
              open={openSources}
              onToggle={toggleSource}
            />
          </div>
        ) : null}
        <div className={styles.areaMessage}>
          <OriginalMessage detail={detail} />
        </div>
      </div>
      <HistoryPanel detail={detail} />
    </section>
  );
}
