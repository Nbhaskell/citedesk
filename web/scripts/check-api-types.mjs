// Fails if src/api/schema.d.ts is not what the generator makes from openapi.json.
// Regenerate with `npm run gen:api` (after `python -m tools.export_openapi` if the API changed).
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("..", import.meta.url));
const generator = join(root, "node_modules", "openapi-typescript", "bin", "cli.js");
const scratch = mkdtempSync(join(tmpdir(), "citedesk-types-"));
const fresh = join(scratch, "schema.d.ts");

try {
  execFileSync(process.execPath, [generator, join(root, "openapi.json"), "-o", fresh], {
    stdio: "ignore",
  });
  const normalise = (text) => text.replace(/\r\n/g, "\n");
  const committed = normalise(readFileSync(join(root, "src", "api", "schema.d.ts"), "utf8"));
  if (committed !== normalise(readFileSync(fresh, "utf8"))) {
    console.error("src/api/schema.d.ts is out of date with openapi.json; run: npm run gen:api");
    process.exitCode = 1;
  } else {
    console.log("src/api/schema.d.ts is current");
  }
} finally {
  rmSync(scratch, { recursive: true, force: true });
}
