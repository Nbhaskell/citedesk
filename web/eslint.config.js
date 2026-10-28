import js from "@eslint/js";
import jsxA11y from "eslint-plugin-jsx-a11y";
import react from "eslint-plugin-react";
import reactHooks from "eslint-plugin-react-hooks";
import globals from "globals";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist", "node_modules", "src/api/schema.d.ts"] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  react.configs.flat.recommended,
  react.configs.flat["jsx-runtime"],
  reactHooks.configs.flat.recommended,
  jsxA11y.flatConfigs.recommended,
  { settings: { react: { version: "detect" } } },
  {
    files: ["src/**/*.{ts,tsx}", "vite.config.ts"],
    languageOptions: { globals: globals.browser },
    rules: {
      // Customer text, model output and source passages are rendered as text, never as HTML
      // (CLAUDE.md rule 5). There is no exception to this rule.
      "react/no-danger": "error",
      "react/no-danger-with-children": "error",
      // No message or draft text in console output (CLAUDE.md rule 4).
      "no-console": "error",
      "react/prop-types": "off",
    },
  },
  {
    files: ["scripts/**/*.mjs", "eslint.config.js"],
    languageOptions: { globals: globals.node },
  },
);
