import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5250,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://localhost:8070',
        // Reading a long document and planning diagrams can take a couple of minutes.
        timeout: 600000,
        proxyTimeout: 600000,
      },
    },
  },
})
