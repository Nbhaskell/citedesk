import { Link } from "react-router-dom";
import { errors } from "../copy";

/** The four screens are built in the next steps; until then each route says what it will hold. */
export function Placeholder({ title, children }: { title: string; children: string }) {
  return (
    <section aria-labelledby="page-title">
      <h1 id="page-title">{title}</h1>
      <p>{children}</p>
    </section>
  );
}

export function QueueScreen() {
  return <Placeholder title="Queue">Inquiries waiting for you will be listed here.</Placeholder>;
}

export function DetailScreen() {
  return (
    <Placeholder title="Inquiry">
      The message, the draft and its checks will be shown here.
    </Placeholder>
  );
}

export function InsightsScreen() {
  return <Placeholder title="Insights">Counts and review times will be shown here.</Placeholder>;
}

export function SettingsScreen() {
  return <Placeholder title="Settings">What is in force will be shown here.</Placeholder>;
}

export function NotFoundScreen() {
  return (
    <section aria-labelledby="page-title">
      <h1 id="page-title">{errors.notFoundTitle}</h1>
      <p>{errors.notFoundBody}</p>
      <p>
        <Link to="/">{errors.backToQueue}</Link>
      </p>
    </section>
  );
}
