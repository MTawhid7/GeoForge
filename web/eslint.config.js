import js from "@eslint/js";
import globals from "globals";
import reactHooks from "eslint-plugin-react-hooks";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist", "public", "src/types/generated"] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ["**/*.{ts,tsx}"],
    languageOptions: { ecmaVersion: 2022, globals: globals.browser },
    plugins: { "react-hooks": reactHooks },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "@typescript-eslint/no-non-null-assertion": "error",
      "@typescript-eslint/consistent-type-imports": "error",
      // docs/06 §6.4: no hardcoded UI strings. Enforced by a unit test over the string table
      // rather than a lint rule, because a rule cannot tell a label from an aria-role name.
    },
  },
  {
    files: ["scripts/**/*.mjs", "*.config.ts"],
    languageOptions: { globals: globals.node },
  },
);
