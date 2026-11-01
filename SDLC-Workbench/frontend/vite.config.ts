import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5270,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://localhost:8090',
        // Agent runs can take minutes.
        timeout: 600000,
        proxyTimeout: 600000,
      },
    },
  },
  // Pure logic and static rendering only: there is no browser and no DOM in the tests.
  test: {
    environment: 'node',
    include: ['src/**/*.test.{ts,tsx}'],
  },
})
