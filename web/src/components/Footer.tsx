import { app } from "../copy";
import { useStatus } from "./StatusProvider";
import styles from "./Footer.module.css";

/**
 * The synthetic-data notice is on every screen. It shows until the API says the data is real:
 * a missing or failed status must never hide it.
 */
export function Footer() {
  const { data } = useStatus();
  const synthetic = data?.synthetic_data !== false;
  return (
    <footer className={styles.footer}>
      {synthetic ? <p className={styles.note}>{app.demoData}</p> : null}
    </footer>
  );
}
