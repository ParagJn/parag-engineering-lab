import { defineConfig } from "vite";

// Frontend on http://localhost:5173; /api is proxied to the FastAPI backend.
const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";

export default defineConfig({
  server: {
    host: "localhost",
    port: 5173,
    strictPort: true,
    open: true,
    proxy: {
      "/api": { target: BACKEND_URL, changeOrigin: true },
    },
  },
  preview: {
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": { target: BACKEND_URL, changeOrigin: true },
    },
  },
});
