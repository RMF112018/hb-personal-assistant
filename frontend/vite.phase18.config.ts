import path from 'node:path'
import { defineConfig, mergeConfig } from 'vite'

import base from './vite.config'

export default mergeConfig(
  base,
  defineConfig({
    server: {
      proxy: {
        '/api': {
          target: 'http://127.0.0.1:8001',
          changeOrigin: true,
          timeout: 120_000,
          proxyTimeout: 120_000,
        },
      },
    },
    root: path.resolve(__dirname),
  }),
)
