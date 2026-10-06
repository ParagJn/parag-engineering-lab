/// <reference types="vitest/config" />
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { port: 5173, strictPort: true },
  // docx + markdown-it make one large chunk; fine for a local tool (Mermaid is split out lazily).
  build: { chunkSizeWarningLimit: 2000 },
  test: { environment: "node" },
});
