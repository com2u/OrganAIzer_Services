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
      },
    },
  },
  // Environment configuration
  define: {
    'import.meta.env.VITE_API_URL': process.env.NODE_ENV === 'production'
      ? '"https://organaizer_backend.com2u.selfhost.eu"'
      : '"http://localhost:8000/api"',
    'import.meta.env.VITE_API_KEY': process.env.VITE_API_KEY
      ? `"${process.env.VITE_API_KEY}"`
      : '""',
  },
})
