import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // Load .env files so VITE_* variables in frontend/.env are available here
  const env = loadEnv(mode, process.cwd(), '')

  // VITE_API_BASE_URL:
  //   Dev  → http://localhost:8000  (direct to backend; WS also works because toWsBase maps it)
  //   Prod → "" (empty = relative; nginx proxies /api/* to backend)
  // Override by setting VITE_API_BASE_URL in frontend/.env
  const apiBaseUrl =
    env.VITE_API_BASE_URL ||
    (mode === 'production' ? '' : 'http://localhost:8000')

  // VITE_API_KEY: must be set in frontend/.env — no fallback.
  // An empty key is passed through; the backend will reject it with 401.
  const apiKey = env.VITE_API_KEY || ''

  return {
    plugins: [react()],
    base: '/',
    build: {
      outDir: 'dist',
      sourcemap: false,
      rollupOptions: {
        output: {
          manualChunks: {
            vendor: ['react', 'react-dom'],
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
    // Build-time replacements — these WIN over .env auto-injection for these vars.
    // VITE_API_BASE_URL and VITE_API_KEY are intentionally set here so the
    // production build embeds the correct values without needing a runtime config.
    define: {
      'import.meta.env.VITE_API_BASE_URL': JSON.stringify(apiBaseUrl),
      'import.meta.env.VITE_API_KEY': JSON.stringify(apiKey),
    },
  }
})
