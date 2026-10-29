import type { Urgency } from "../api/types";
import { urgency as words } from "../copy";
import styles from "./UrgencyTag.module.css";

/** The urgency as a word. Colour and the row's edge band repeat it; they never replace it. */
export function UrgencyTag({ urgency }: { urgency: Urgency }) {
  return <span className={`${styles.tag} ${styles[urgency]}`}>{words[urgency]}</span>;
}
