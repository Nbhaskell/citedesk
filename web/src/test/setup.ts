import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";
import { forgetViewed } from "../screens/queue/returnFocus";

afterEach(() => {
  cleanup();
  forgetViewed();
  // A few test files run in the Node environment, which has no document.
  if (typeof document !== "undefined") document.title = "";
});
