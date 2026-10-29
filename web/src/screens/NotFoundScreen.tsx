import { Link } from "react-router-dom";
import { errors } from "../copy";

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
