import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  server: {
    port: 5174,
    proxy: {
      // The console talks to the API through a same-origin proxy in dev, so
      // the Authorization header and CORS behave exactly as they will behind
      // Vercel's rewrite in production (infra/vercel.json).
      "/api": { target: "http://localhost:8000", changeOrigin: true },
      "/health": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
});
