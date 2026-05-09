import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': new URL('./src', import.meta.url).pathname,
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/agent': 'http://localhost:8000',
      '/graph': 'http://localhost:8000',
      '/api': 'http://localhost:8000',
      '/files': 'http://localhost:8000',
      '/webhooks': 'http://localhost:8000',
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/tests/setup.ts',
  },
})
