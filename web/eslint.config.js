import js from "@eslint/js";
import { fixupPluginRules } from "@eslint/compat";
import globals from "globals";
import tseslint from "typescript-eslint";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import griffel from "@griffel/eslint-plugin";
import fluentA11y from "@microsoft/eslint-plugin-fluentui-jsx-a11y";

export default tseslint.config(
  { ignores: ["dist", "node_modules", "src/lib/fixture.json"] },
  {
    files: ["src/**/*.{ts,tsx}"],
    extends: [js.configs.recommended, ...tseslint.configs.strict],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "module",
      globals: globals.browser,
    },
    plugins: {
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
      // Fluent UI v9 accessibility rules (apt for an accessibility-focused product).
      // fixupPluginRules bridges 3.0.0-alpha.3's ESLint-8-only API calls (e.g.
      // context.getAncestors() inside the tooltip check) onto ESLint 9.
      "@microsoft/fluentui-jsx-a11y": fixupPluginRules(fluentA11y),
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      ...fluentA11y.configs.recommended.rules,
      // Strict policy: no warnings — promote every warn-level rule to error.
      "react-hooks/exhaustive-deps": "error",
      "react-refresh/only-export-components": ["error", { allowConstantExport: true }],
      "@microsoft/fluentui-jsx-a11y/prefer-aria-over-title-attribute": "error",
      "@microsoft/fluentui-jsx-a11y/visual-label-better-than-aria-suggestion": "error",
    },
  },
  {
    // Griffel: hardens makeStyles() usage (longhands, hook naming, top-level styles).
    files: ["src/**/*.{ts,tsx}"],
    ...griffel.configs.recommended,
  },
);
