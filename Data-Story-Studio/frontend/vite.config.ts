import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5190,
    strictPort: true,
    proxy: { "/api": { target: "http://localhost:8020", timeout: 300000, proxyTimeout: 300000 } },
  },
  build: { chunkSizeWarningLimit: 2000 },
});
