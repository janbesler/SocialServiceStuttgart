import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  base: "./",
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      strategies: "generateSW",
      workbox: {
        globPatterns: ["**/*.{js,css,html,ico,png,svg,webp}"],
        runtimeCaching: [
          {
            urlPattern: /^https:\/\/tile\.openstreetmap\.org\/.*/i,
            handler: "CacheFirst",
            options: {
              cacheName: "osm-tiles",
              expiration: {
                maxEntries: 200,
                maxAgeSeconds: 60 * 60 * 24 * 30,
              },
            },
          },
          {
            urlPattern: /\/data\/.*\.geojson$/,
            handler: "CacheFirst",
            options: {
              cacheName: "geojson-data",
              expiration: {
                maxEntries: 10,
                maxAgeSeconds: 60 * 60 * 24 * 7,
              },
            },
          },
        ],
      },
      manifest: {
        name: "Aufwachsindex Stuttgart",
        short_name: "Aufwachsindex",
        description:
          "Interaktives Dashboard zu Aufwachsbedingungen in Stuttgart",
        start_url: "./",
        display: "standalone",
        theme_color: "#1e3a5f",
        background_color: "#ffffff",
        orientation: "portrait-primary",
        icons: [
          {
            src: "icons/icon-192.png",
            sizes: "192x192",
            type: "image/png",
          },
          {
            src: "icons/icon-512.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "any maskable",
          },
        ],
      },
    }),
  ],
  build: {
    chunkSizeWarningLimit: 1200,
    rollupOptions: {
      output: {
        manualChunks: {
          "vendor-react": ["react", "react-dom"],
          "vendor-maplibre": ["maplibre-gl"],
          "vendor-recharts": ["recharts"],
          "vendor-zustand": ["zustand"],
        },
      },
    },
  },
  server: {
    fs: {
      allow: ["../.."],
    },
  },
});
