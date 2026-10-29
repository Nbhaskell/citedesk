import { useEffect, useId, useRef, type FormEvent } from "react";
import { ApiError } from "../../api/client";
import { errors } from "../../copy";
import styles from "./Detail.module.css";

/**
 * A short form that opens under the buttons, not a dialog (brief: destructive actions ask for a
 * reason, not a confirmation). A form the person opened takes focus (`focusOnOpen`); one that is
 * simply part of the page must not, or it would swallow j, k and Escape the moment the page loads.
 * The text stays in the caller's state, so a failed save loses nothing.
 */
export function InlineForm({
  label,
  value,
  onChange,
  onSubmit,
  onCancel,
  submitLabel,
  cancelLabel,
  required,
  invalid,
  invalidMessage,
  busy = false,
  maxLength = 500,
  focusOnOpen = false,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  onCancel?: () => void;
  submitLabel: string;
  cancelLabel?: string;
  required: boolean;
  invalid: boolean;
  invalidMessage: string;
  busy?: boolean;
  maxLength?: number;
  focusOnOpen?: boolean;
}) {
  const field = useRef<HTMLTextAreaElement>(null);
  const id = useId();
  const messageId = `${id}-message`;

  useEffect(() => {
    if (focusOnOpen) field.current?.focus();
  }, [focusOnOpen]);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    onSubmit();
  };

  return (
    <form className={styles.inline} onSubmit={submit} noValidate>
      <label htmlFor={id} className={styles.label}>
        {label}
      </label>
      <textarea
        id={id}
        ref={field}
        rows={3}
        value={value}
        maxLength={maxLength}
        required={required}
        aria-invalid={invalid}
        aria-describedby={invalid ? messageId : undefined}
        onChange={(event) => onChange(event.target.value)}
      />
      {invalid ? (
        <p id={messageId} className={styles.fieldError}>
          {invalidMessage}
        </p>
      ) : null}
      <div className={styles.buttons}>
        <button type="submit" className={styles.secondary} disabled={busy}>
          {submitLabel}
        </button>
        {onCancel ? (
          <button type="button" className={styles.linkButton} onClick={onCancel}>
            {cancelLabel}
          </button>
        ) : null}
      </div>
    </form>
  );
}

/** A failed request, in words, with the request number so it can be found in the logs. */
export function ErrorNote({ error, lead }: { error: ApiError; lead?: string }) {
  return (
    <p role="alert" className={styles.errorNote}>
      {lead ? `${lead} ` : ""}
      {error.unreachable ? errors.unreachable : error.message}
      {error.requestId ? (
        <span className={styles.faint}>
          {" "}
          ({errors.requestId} {error.requestId})
        </span>
      ) : null}
    </p>
  );
}
