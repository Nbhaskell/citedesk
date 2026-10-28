import { Link } from "react-router-dom";
import type { InquirySummary } from "../../api/types";
import { UrgencyTag } from "../../components/UrgencyTag";
import { queue as words, stateWords } from "../../copy";
import { ageText, exactText } from "../../lib/age";
import styles from "./Queue.module.css";

/**
 * One inquiry. The whole row is the link. Everything shown here that came from a customer or the
 * model (summary, subject, name) is rendered as text by React, never as markup.
 */
export function QueueRow({ item, now }: { item: InquirySummary; now: number }) {
  const edge = item.urgency ?? "none";
  return (
    <li className={`${styles.item} ${styles[`edge_${edge}`]}`}>
      <Link to={`/inquiries/${item.id}`} className={styles.row} data-row>
        <span className={styles.urgency}>
          {item.urgency ? <UrgencyTag urgency={item.urgency} /> : null}
        </span>
        <span className={styles.state}>{stateWords(item.status, item.route)}</span>
        <span className={styles.summary}>{item.summary ?? item.subject ?? words.noSubject}</span>
        <span className={styles.sender}>{item.sender_name ?? words.unknownSender}</span>
        <time
          className={styles.age}
          dateTime={item.received_at}
          title={exactText(item.received_at)}
        >
          {ageText(item.received_at, now)}
        </time>
        {item.duplicate_of !== null ? <span className={styles.repeat}>{words.repeat}</span> : null}
      </Link>
    </li>
  );
}

/** A grey shape where a row will be. It says nothing and is hidden from screen readers. */
export function QueueRowPlaceholder() {
  return (
    <li className={`${styles.item} ${styles.edge_none}`} aria-hidden="true">
      <div className={styles.row}>
        <span className={styles.bar} style={{ width: "4rem" }} />
        <span className={styles.bar} style={{ width: "7rem" }} />
        <span className={styles.bar} style={{ width: "70%" }} />
        <span className={styles.bar} style={{ width: "6rem" }} />
        <span className={styles.bar} style={{ width: "3rem" }} />
      </div>
    </li>
  );
}
