/// <reference types="node" />
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import { defineConfig, type Plugin } from "vite";
import headers from "./security-headers.json";

// Film Room posts (src/film-room/posts/*.md) as the module "virtual:film-room".
// Drafts are included only by the dev server, so a production build never
// contains a draft's text, not even in the JavaScript.
const POSTS_DIR = fileURLToPath(new URL("./src/film-room/posts", import.meta.url));
const VIRTUAL = "\0virtual:film-room";
const isDraft = (raw: string) => /^draft:\s*true\s*$/m.test(raw.match(/^---\r?\n([\s\S]*?)\r?\n---/)?.[1] ?? "");

function filmRoom(): Plugin {
  let drafts = false;
  return {
    name: "film-room",
    configResolved(config) {
      drafts = config.command === "serve";
    },
    resolveId: (id) => (id === "virtual:film-room" ? VIRTUAL : undefined),
    load(id) {
      if (id !== VIRTUAL) return;
      const posts = readdirSync(POSTS_DIR)
        .filter((f) => f.endsWith(".md"))
        .map((f) => ({ slug: f.slice(0, -3), raw: readFileSync(join(POSTS_DIR, f), "utf8") }))
        .filter((p) => drafts || !isDraft(p.raw));
      return `export default ${JSON.stringify(posts)};`;
    },
    configureServer(server) {
      // New, edited or deleted posts show up without restarting `make web`.
      server.watcher.add(POSTS_DIR);
      const reload = (file: string) => {
        if (!file.startsWith(POSTS_DIR)) return;
        const mod = server.moduleGraph.getModuleById(VIRTUAL);
        if (mod) server.moduleGraph.invalidateModule(mod);
        server.ws.send({ type: "full-reload" });
      };
      for (const event of ["add", "change", "unlink"]) server.watcher.on(event, reload);
    },
  };
}

// The headers Render sends with the site (render.yaml), so `npm run preview`
// shows exactly what production allows; locally the API is on 127.0.0.1:8000.
const local = "connect-src 'self' http://127.0.0.1:8000 ws://127.0.0.1:8000";
const previewHeaders = {
  ...headers,
  "Content-Security-Policy": headers["Content-Security-Policy"].replace("connect-src 'self'", local),
};

export default defineConfig({
  plugins: [react(), filmRoom()],
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
