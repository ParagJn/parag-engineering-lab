import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5240,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://localhost:8060',
        // Comparing large files with a long model call can take minutes.
        timeout: 600000,
        proxyTimeout: 600000,
      },
    },
  },
})
