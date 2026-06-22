import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // Proxy /api calls to local FastAPI analytics shell during `npm run dev`.
      // Run backend with: pip install -e '.[analytics-ui]' && uvicorn hb_assistant.construction.analytics.api:create_app --factory --reload --port 8000
      // Or set VITE_API_BASE in .env (e.g. http://localhost:8000) and update the client to honor it.
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        timeout: 120_000,
        proxyTimeout: 120_000,
      },
    },
  },
})
