import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import headers from "./security-headers.json";

// The headers Render sends with the site (render.yaml), so `npm run preview`
// shows exactly what production allows; locally the API is on 127.0.0.1:8000.
const local = "connect-src 'self' http://127.0.0.1:8000 ws://127.0.0.1:8000";
const previewHeaders = {
  ...headers,
  "Content-Security-Policy": headers["Content-Security-Policy"].replace("connect-src 'self'", local),
};

export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
  preview: { port: 4173, headers: previewHeaders },
  build: {
    rollupOptions: {
      output: {
        // Vendor code changes rarely; keep it out of the app chunk so deploys
        // only bust the cache for what changed.
        manualChunks: {
          react: ["react", "react-dom", "react-router-dom"],
          charts: ["recharts"],
        },
      },
    },
  },
});
