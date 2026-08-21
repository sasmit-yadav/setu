import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      strategies: "injectManifest",
      srcDir: "src",
      filename: "sw.ts",
      registerType: "autoUpdate",
      injectRegister: "auto",
      devOptions: { enabled: true, type: "module" },
      manifest: {
        name: "SETU Citizen",
        short_name: "SETU",
        description: "Disaster alerts — acknowledge and respond",
        theme_color: "#f3f2f1",
        background_color: "#f3f2f1",
        display: "standalone",
        start_url: "/",
        // 192 is the install icon, 512 is what Android uses for the splash
        // screen. Both are also declared `maskable`: the glyph is drawn inside
        // the central 60% of the canvas (scripts/gen_pwa_icons.py), so a
        // circular crop cannot clip it. Without a 512 Chrome will not offer
        // "add to home screen" at all, which is the entry point for the whole
        // offline story.
        icons: [
          {
            src: "/icon-192.png",
            sizes: "192x192",
            type: "image/png",
            purpose: "any maskable",
          },
          {
            src: "/icon-512.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "any maskable",
          },
        ],
      },
    }),
  ],
  server: {
    port: 5174,
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
});
