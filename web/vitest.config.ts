import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// Standalone Vitest config (takes precedence over vite.config.ts when running tests).
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "happy-dom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
    css: false,
  },
});
