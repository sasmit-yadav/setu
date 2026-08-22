import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  optimizeDeps: {
    exclude: ["maplibre-gl"],
  },
  worker: {
    format: "es",
  },
  server: {
    port: 5173,
    proxy: {
      // Local same-origin proxy. Deployed console uses VITE_API_BASE (Render)
      // the same way the citizen PWA does — Vercel is static files, not a rewrite.
      "/api": { target: "http://localhost:8000", changeOrigin: true, ws: true },
      "/health": { target: "http://localhost:8000", changeOrigin: true, ws: true },
      "/ofm": {
        target: "https://tiles.openfreemap.org",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/ofm/, ""),
      },
    },
  },
  plugins: [react()],
});
