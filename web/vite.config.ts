import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev server and production preview both bind to 9711 for a stable local URL.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 9711,
    strictPort: true,
  },
  preview: {
    port: 9711,
    strictPort: true,
  },
});
