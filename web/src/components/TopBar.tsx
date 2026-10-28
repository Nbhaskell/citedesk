import { Link, NavLink } from "react-router-dom";
import { app, connection, nav, urgentChip } from "../copy";
import { useStatus } from "./StatusProvider";
import styles from "./TopBar.module.css";

export function TopBar() {
  const { data, error } = useStatus();
  const urgent = data?.attention.urgent_open ?? 0;

  return (
    <header className={styles.bar}>
      <Link to="/" className={styles.brand}>
        {app.name}
      </Link>
      <nav aria-label={nav.label} className={styles.nav}>
        <NavLink to="/" end className={styles.link}>
          {nav.queue}
        </NavLink>
        <NavLink to="/insights" className={styles.link}>
          {nav.insights}
        </NavLink>
        <NavLink to="/settings" className={styles.link}>
          {nav.settings}
        </NavLink>
      </nav>
      <div className={styles.right}>
        {data && urgent > 0 ? (
          <Link
            to="/?urgency=urgent"
            className={styles.urgent}
            aria-label={urgentChip.label(urgent)}
          >
            {urgentChip.some(urgent)}
          </Link>
        ) : data ? (
          <span className={styles.quiet}>{urgentChip.none}</span>
        ) : null}
        {error ? <span className={styles.lost}>{connection.lost}</span> : null}
      </div>
    </header>
  );
}
