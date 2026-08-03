import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    // e2e/ is Playwright's; running it under vitest would start a browser inside jsdom.
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
  },
});
