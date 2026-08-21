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
      // The console talks to the API through a same-origin proxy in dev, so
      // the Authorization header and CORS behave exactly as they will behind
      // Vercel's rewrite in production (infra/vercel.json).
      "/api": { target: "http://localhost:8000", changeOrigin: true, ws: true },
      "/health": { target: "http://localhost:8000", changeOrigin: true, ws: true },
    },
  },
  plugins: [react()],
});
