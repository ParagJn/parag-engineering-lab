import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5180,
    strictPort: true,
    proxy: { "/api": "http://localhost:8010" },
  },
  // pptxgenjs is large; fine for a local tool.
  build: { chunkSizeWarningLimit: 2000 },
});
