import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(() => {
  cleanup();
  // A few test files run in the Node environment, which has no document.
  if (typeof document !== "undefined") document.title = "";
});
