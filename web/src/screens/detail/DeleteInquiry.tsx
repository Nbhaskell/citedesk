import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError } from "../../api/client";
import { useApi } from "../../api/context";
import { useAnnounce } from "../../components/LiveRegion";
import { detail as words } from "../../copy";
import { ErrorNote } from "./forms";
import styles from "./Detail.module.css";

/**
 * Delete the inquiry for good (D-101). The first button only asks; the second, named for its
 * consequence, deletes. After deleting, the queue is shown, since this page no longer exists.
 */
export function DeleteInquiry({ inquiryId }: { inquiryId: number }) {
  const api = useApi();
  const navigate = useNavigate();
  const announce = useAnnounce();
  const [asking, setAsking] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const confirmRef = useRef<HTMLButtonElement>(null);
  const openRef = useRef<HTMLButtonElement>(null);
  const text = words.remove;

  // Focus follows the step: onto the confirming button when asked, back when called off.
  const moved = useRef(false);
  useEffect(() => {
    if (!moved.current) return;
    (asking ? confirmRef : openRef).current?.focus();
  }, [asking]);

  const ask = () => {
    setError(null);
    moved.current = true;
    setAsking(true);
  };
  const cancel = () => setAsking(false);
  const remove = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.deleteInquiry(inquiryId);
      announce(text.done(inquiryId));
      navigate("/", { replace: true });
    } catch (caught) {
      const failure =
        caught instanceof ApiError
          ? caught
          : new ApiError(0, "unexpected", "Something went wrong in the page.", null);
      setError(failure);
      announce(failure.message, { assertive: true });
      setBusy(false);
    }
  };

  return (
    <section className={styles.panel} aria-labelledby="delete-title">
      <h2 id="delete-title">{text.title}</h2>
      <p className={styles.meta}>{text.hint}</p>
      {error ? <ErrorNote error={error} /> : null}
      {asking ? (
        <div role="group" aria-labelledby="delete-confirm">
          <p id="delete-confirm">{text.confirm}</p>
          <div className={styles.buttons}>
            <button
              ref={confirmRef}
              type="button"
              className={styles.secondary}
              disabled={busy}
              onClick={() => void remove()}
            >
              {busy ? text.busy : text.confirmButton}
            </button>
            <button type="button" className={styles.secondary} disabled={busy} onClick={cancel}>
              {text.cancel}
            </button>
          </div>
        </div>
      ) : (
        <div className={styles.buttons}>
          <button ref={openRef} type="button" className={styles.secondary} onClick={ask}>
            {text.button}
          </button>
        </div>
      )}
    </section>
  );
}
