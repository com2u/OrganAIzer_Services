import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  base: '/',
  build: {
    outDir: 'dist',
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom', 'react-router-dom'],
        },
      },
    },
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
        ws: true,   // ← forward WebSocket upgrades (voice mode WS)
      },
    },
  },
  // Environment configuration
  define: {
    'import.meta.env.VITE_API_URL': process.env.NODE_ENV === 'production'
      ? '"https://organaizer_backend.com2u.selfhost.eu"'
      : '"http://localhost:8000/api"',
    // VITE_API_BASE_URL drives both REST fetch() calls and the WebSocket URL
    // (see apiClient.ts → toWsBase).  In dev we point directly at the backend
    // so the WS base becomes ws://localhost:8000 — no Vite-proxy involvement.
    // In prod the origin already matches the backend, so '' (relative) is fine
    // and nginx handles /api/* → backend.
    'import.meta.env.VITE_API_BASE_URL': process.env.NODE_ENV === 'production'
      ? '""'
      : '"http://localhost:8000"',
    'import.meta.env.VITE_API_KEY': process.env.VITE_API_KEY
      ? `"${process.env.VITE_API_KEY}"`
      : '""',
  },
})
