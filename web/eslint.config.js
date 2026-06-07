import js from "@eslint/js";
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
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "module",
      globals: globals.browser,
    },
    plugins: {
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
      // Fluent UI v9 accessibility rules (apt for an accessibility-focused product).
      "@microsoft/fluentui-jsx-a11y": fluentA11y,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      ...fluentA11y.configs.recommended.rules,
      "react-refresh/only-export-components": ["warn", { allowConstantExport: true }],
    },
  },
  {
    // Griffel: hardens makeStyles() usage (longhands, hook naming, top-level styles).
    files: ["src/**/*.{ts,tsx}"],
    ...griffel.configs.recommended,
  },
);
