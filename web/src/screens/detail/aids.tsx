import type { InquiryDetail } from "../../api/types";
import { detail as words } from "../../copy";
import styles from "./Detail.module.css";

type Support = NonNullable<InquiryDetail["support"]>;

function firstName(name: string | null | undefined): string | null {
  const parts = (name ?? "").trim().split(/\s+/).filter(Boolean);
  const titles = new Set(["mr", "mrs", "ms", "miss", "mx", "dr", "prof"]);
  const first = parts.find((p, i) => !(i === 0 && titles.has(p.toLowerCase().replace(/\.$/, ""))));
  return first ? first.replace(/[.,]$/, "") : null;
}

/**
 * What to compare with the sources before approving: the name in the greeting beside the sender,
 * the line each figure comes from, and the sentences no passage backs. Computed in code on the
 * server from the stored draft; shown as text only. It never blocks anything.
 */
export function ReadingAids({
  support,
  senderName,
  senderEmail,
  onOpenSource,
}: {
  support: Support;
  senderName: string | null;
  senderEmail: string | null;
  onOpenSource: (index: number) => void;
}) {
  const marked = support.sentences.filter((s) => s.status === "unsupported");
  const tone = support.sentences.filter((s) => s.status === "tone");
  const asksKnown = support.sentences.filter((s) => s.status === "asks_known");
  const sender = firstName(senderName);
  const differs =
    support.greeting_name !== null &&
    sender !== null &&
    support.greeting_name.toLowerCase() !== sender.toLowerCase();
  return (
    <section className={styles.aids} aria-labelledby="aids-title">
      <h3 id="aids-title">{words.aids.title}</h3>
      <p className={styles.meta}>{words.aids.intro}</p>

      <p>
        <span className={styles.label}>{words.aids.greeting}:</span>{" "}
        <strong>{support.greeting_name ?? words.aids.greetingNone}</strong>
        {" · "}
        <span className={styles.label}>{words.aids.sender}:</span>{" "}
        <strong>{senderName ?? words.aids.senderNone}</strong>
        {senderEmail ? <span className={styles.faint}> ({senderEmail})</span> : null}
      </p>
      {differs ? (
        <p className={styles.warn} role="note">
          {words.aids.nameDiffers}
        </p>
      ) : null}

      <h4>{words.aids.figures}</h4>
      {support.figures.length === 0 ? (
        <p className={styles.faint}>{words.aids.noFigures}</p>
      ) : (
        <ul className={styles.aidList}>
          {support.figures.map((figure) => (
            <li key={`${figure.figure}-${figure.sentence}`}>
              <strong>{figure.figure}</strong>{" "}
              {figure.origins.length === 0 ? (
                figure.from_message ? (
                  <span>{words.aids.fromMessage}</span>
                ) : (
                  <span className={styles.warn}>{words.aids.noOrigin}</span>
                )
              ) : (
                figure.origins.map((origin) => (
                  <span key={origin.source_index} className={styles.origin}>
                    {words.aids.from} {origin.file} › {origin.section}: “{origin.line}”{" "}
                    <button
                      type="button"
                      className={styles.marker}
                      onClick={() => onOpenSource(origin.source_index)}
                      aria-label={words.aids.open(origin.source_index)}
                    >
                      [{origin.source_index}]
                    </button>
                  </span>
                ))
              )}
              {figure.mismatch ? (
                <span className={styles.warn}> {words.aids.otherLine}</span>
              ) : null}
            </li>
          ))}
        </ul>
      )}

      <h4>
        {words.aids.unsourced}{" "}
        <span className={styles.faint}>
          ({words.aids.count(marked.length, support.sentences.length)})
        </span>
      </h4>
      {marked.length === 0 ? (
        <p className={styles.faint}>{words.aids.noneMarked}</p>
      ) : (
        <ul className={styles.aidList}>
          {marked.map((sentence) => (
            <li key={sentence.text}>
              <span className={styles.warn}>{words.aids.unsourcedMark}:</span> {sentence.text}
            </li>
          ))}
        </ul>
      )}

      {asksKnown.length > 0 ? (
        <>
          <h4>{words.aids.asksKnown}</h4>
          <p className={styles.faint}>{words.aids.asksKnownNote}</p>
          <ul className={styles.aidList}>
            {asksKnown.map((sentence) => (
              <li key={sentence.text}>
                <span className={styles.warn}>
                  {words.aids.asksKnownFor(sentence.asks_for ?? [])}:
                </span>{" "}
                {sentence.text}
              </li>
            ))}
          </ul>
        </>
      ) : null}

      {tone.length > 0 ? (
        <>
          <h4>{words.aids.tone}</h4>
          <p className={styles.faint}>{words.aids.toneNote}</p>
          <ul className={styles.aidList}>
            {tone.map((sentence) => (
              <li key={sentence.text}>
                <span className={styles.warn}>{words.aids.toneMark}:</span> {sentence.text}
              </li>
            ))}
          </ul>
        </>
      ) : null}
    </section>
  );
}
