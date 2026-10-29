// @vitest-environment node
import { ESLint } from "eslint";
import { describe, expect, it } from "vitest";

// The two lint rules that carry safety rules (CLAUDE.md rules 4 and 5) must keep failing the build.
async function rulesBroken(code: string): Promise<string[]> {
  const eslint = new ESLint();
  const [result] = await eslint.lintText(code, { filePath: "src/example.tsx" });
  return (result?.messages ?? []).filter((m) => m.severity === 2).map((m) => m.ruleId ?? "");
}

describe("lint rules that protect the safety rules", () => {
  it("refuses to put text into the page as HTML", async () => {
    const code =
      "export const A = ({ x }: { x: string }) => <div dangerouslySetInnerHTML={{ __html: x }} />;\n";
    expect(await rulesBroken(code)).toContain("react/no-danger");
  });

  it("refuses console output, where message text could leak", async () => {
    const code = "export function f(text: string) {\n  console.log(text);\n}\n";
    expect(await rulesBroken(code)).toContain("no-console");
  });

  it("accepts plain text rendering", async () => {
    const code = "export const A = ({ x }: { x: string }) => <p>{x}</p>;\n";
    expect(await rulesBroken(code)).toEqual([]);
  });
});
