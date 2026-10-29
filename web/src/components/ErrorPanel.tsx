import type { ApiError } from "../api/client";
import { errors } from "../copy";
import styles from "./ErrorPanel.module.css";

/** A screen that could not load: what happened, the request number if there is one, and Retry. */
export function ErrorPanel({ error, onRetry }: { error: ApiError | null; onRetry: () => void }) {
  return (
    <div className={styles.panel}>
      <p>{error && !error.unreachable ? error.message : errors.unreachable}</p>
      {error?.requestId ? (
        <p className={styles.meta}>
          {errors.requestId} {error.requestId}
        </p>
      ) : null}
      <button type="button" className={styles.button} onClick={onRetry}>
        {errors.retry}
      </button>
    </div>
  );
}
