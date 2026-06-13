import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Dev server and production preview both bind to 9711 for a stable local URL.
// `base` is "/" locally; the GitHub Pages workflow sets PAGES_BASE=/PathForward/
// so built asset URLs resolve under the repo subpath.
export default defineConfig({
  base: process.env.PAGES_BASE || "/",
  plugins: [react(), tailwindcss()],
  server: {
    port: 9711,
    strictPort: true,
  },
  preview: {
    port: 9711,
    strictPort: true,
  },
});
