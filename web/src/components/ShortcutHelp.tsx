import { useEffect, useRef } from "react";
import { shortcuts as words } from "../copy";
import { setModalOpen } from "../hooks/modal";
import { shortcutsEnabled } from "../hooks/shortcuts";
import styles from "./ShortcutHelp.module.css";

/**
 * The keys, by where they work. Mounted only while open: opening takes focus to the dialog and
 * tells the page behind to ignore keys; closing gives focus back to whatever had it.
 */
export function ShortcutHelp({ onClose }: { onClose: () => void }) {
  const box = useRef<HTMLDivElement>(null);
  const close = useRef<HTMLButtonElement>(null);
  const onCloseRef = useRef(onClose);
  useEffect(() => {
    onCloseRef.current = onClose;
  });

  useEffect(() => {
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    setModalOpen(true);
    // Focus the dialog, not Close: Close is at the bottom, and focusing it would scroll the
    // title out of view on a short screen.
    box.current?.focus();

    // Capture phase on the document, so the dialog sees the key before the screen behind it.
    // Escape and ? close it; Tab stays put because Close is the only control.
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape" || event.key === "?") {
        event.preventDefault();
        event.stopPropagation();
        onCloseRef.current();
      } else if (event.key === "Tab") {
        event.preventDefault();
        close.current?.focus();
      }
    };
    document.addEventListener("keydown", onKey, true);
    return () => {
      document.removeEventListener("keydown", onKey, true);
      setModalOpen(false);
      opener?.focus();
    };
  }, []);

  return (
    <div
      role="presentation"
      className={styles.backdrop}
      data-testid="shortcut-backdrop"
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        ref={box}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-labelledby="shortcut-title"
        className={styles.dialog}
      >
        <h2 id="shortcut-title">{words.title}</h2>
        <p>{words.intro}</p>
        {shortcutsEnabled() ? null : <p className={styles.off}>{words.switchedOff}</p>}
        {words.groups.map((group) => (
          <section key={group.title} className={styles.group}>
            <h3>{group.title}</h3>
            <dl>
              {group.keys.map((entry) => (
                <div key={entry.key + entry.does} className={styles.entry}>
                  <dt>
                    <kbd className={styles.key}>{entry.key}</kbd>
                  </dt>
                  <dd>{entry.does}</dd>
                </div>
              ))}
            </dl>
          </section>
        ))}
        <button ref={close} type="button" className={styles.close} onClick={onClose}>
          {words.close}
        </button>
      </div>
    </div>
  );
}
