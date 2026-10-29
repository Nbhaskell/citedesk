import { app, shortcuts } from "../copy";
import { useStatus } from "./StatusProvider";
import styles from "./Footer.module.css";

/**
 * The synthetic-data notice is on every screen. It shows until the API says the data is real:
 * a missing or failed status must never hide it. Beside it, the way to the shortcut list for
 * anyone who cannot or does not want to press ?.
 */
export function Footer({ onOpenShortcuts }: { onOpenShortcuts: () => void }) {
  const { data } = useStatus();
  const synthetic = data?.synthetic_data !== false;
  return (
    <footer className={styles.footer}>
      {synthetic ? <p className={styles.note}>{app.demoData}</p> : <span />}
      <button type="button" className={styles.shortcuts} onClick={onOpenShortcuts}>
        {shortcuts.open}
      </button>
    </footer>
  );
}
