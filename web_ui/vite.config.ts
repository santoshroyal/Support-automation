import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'node:path'

// Proxy /api/* to the FastAPI dev server so the SPA can talk to the
// real backend during `npm run dev` without CORS gymnastics. In
// production the same SPA is served by FastAPI itself, so the proxy
// only exists in dev.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8080',
        changeOrigin: true,
      },
    },
  },
})
