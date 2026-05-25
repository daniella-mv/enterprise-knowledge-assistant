import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// Vite dev-server proxies /api/* and /health to the backend so the
// browser doesn't deal with CORS and we can use relative URLs in fetch().
//
//   - In Docker:        VITE_API_URL=http://api:8000
//   - Outside Docker:   VITE_API_URL=http://localhost:8000 (or unset)
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const apiTarget = env.VITE_API_URL || 'http://localhost:8000'

  return {
    plugins: [react()],
    server: {
      port: 5173,
      host: '0.0.0.0',
      proxy: {
        '/api': { target: apiTarget, changeOrigin: true },
        '/health': { target: apiTarget, changeOrigin: true },
      },
    },
    build: {
      outDir: 'dist',
      sourcemap: true,
    },
  }
})
