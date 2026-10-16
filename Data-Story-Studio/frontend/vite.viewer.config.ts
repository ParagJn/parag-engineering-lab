import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Single-file IIFE bundle embedded into exported HTML reports (works offline).
export default defineConfig({
  plugins: [react(), tailwindcss()],
  define: { "process.env.NODE_ENV": JSON.stringify("production") },
  build: {
    outDir: "dist-viewer",
    emptyOutDir: true,
    cssCodeSplit: false,
    chunkSizeWarningLimit: 3000,
    lib: {
      entry: "src/viewer.tsx",
      name: "DashboardViewer",
      formats: ["iife"],
      fileName: () => "viewer.js",
    },
  },
});
